"""Reduce repeated CPU texture bindings and invariant blend state writes.

The render thread owns the cache. External drawing and state-block restoration
invalidate it; failed SDK calls never publish a cached binding.
"""


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Backend CPU source anchor drift: ' + before[:80])
    return source.replace(before, after, 1)


def project(source):
    source = replace_once(source, 'struct NativeStateCache {', '''struct NativeStateCache {
    IDirect3DTexture9* texture[6];
    bool texture_valid[6];''')
    source = replace_once(source, '''        native_state.sampler_valid[i] = false;
    }
    native_state.constants_valid''', '''        native_state.sampler_valid[i] = false;
        native_state.texture_valid[i] = false;
    }
    native_state.constants_valid''')
    source = replace_once(source,
        'HRESULT SetNativeTexture(int tile, IDirect3DTexture9* texture) {',
        'HRESULT WriteNativeTexture(int tile, IDirect3DTexture9* texture) {')
    marker = '__declspec(noinline) void VerifyNativeSampler('
    wrapper = '''HRESULT SetNativeTexture(int tile, IDirect3DTexture9* texture) {
    if (tile < 0 || tile >= 6)
        return E_INVALIDARG;
    if (native_state.texture_valid[tile] && native_state.texture[tile] == texture)
        return S_OK;
    const HRESULT result = WriteNativeTexture(tile, texture);
    if (SUCCEEDED(result)) {
        native_state.texture[tile] = texture;
        native_state.texture_valid[tile] = true;
    } else {
        native_state.texture_valid[tile] = false;
    }
    return result;
}
'''
    source = replace_once(source, marker, wrapper + marker)
    source = replace_once(source, '''void SelectTexture(int tile, uint32_t id) {
    draw_state_prepared = false;
    if (tile < 0 || tile > 5 || id >= textures.size())
        Shipyard_Fatal("texture index", E_INVALIDARG);
    upload_tile = tile;''', '''void SelectTexture(int tile, uint32_t id) {
    if (tile < 0 || tile > 5 || id >= textures.size())
        Shipyard_Fatal("texture index", E_INVALIDARG);
    if (selected_fb[tile] >= 0 || selected[tile] != id ||
        !native_state.texture_valid[tile] || native_state.texture[tile] != textures[id].native)
        draw_state_prepared = false;
    upload_tile = tile;''')
    source = replace_once(source, '''    xenos_device->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_SRCALPHA);
    xenos_device->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
    xenos_device->SetRenderState(D3DRS_BLENDOP, D3DBLENDOP_ADD);''', '')
    source = replace_once(source, '''    xenos_device->SetRenderState(D3DRS_SEPARATEALPHABLENDENABLE, TRUE);
    xenos_device->SetRenderState(D3DRS_SRCBLENDALPHA, D3DBLEND_ZERO);
    xenos_device->SetRenderState(D3DRS_DESTBLENDALPHA, D3DBLEND_ONE);
    xenos_device->SetRenderState(D3DRS_BLENDOPALPHA, D3DBLENDOP_ADD);''', '''    if (!native_state.alpha_valid) {
        xenos_device->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_SRCALPHA);
        xenos_device->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
        xenos_device->SetRenderState(D3DRS_BLENDOP, D3DBLENDOP_ADD);
        xenos_device->SetRenderState(D3DRS_SEPARATEALPHABLENDENABLE, TRUE);
        xenos_device->SetRenderState(D3DRS_SRCBLENDALPHA, D3DBLEND_ZERO);
        xenos_device->SetRenderState(D3DRS_DESTBLENDALPHA, D3DBLEND_ONE);
        xenos_device->SetRenderState(D3DRS_BLENDOPALPHA, D3DBLENDOP_ADD);
    }''')
    return source
