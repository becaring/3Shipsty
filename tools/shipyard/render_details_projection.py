"""Attribute every projected Flush call and texture boundary to opt-in counts.

Unknown Flush sites stop projection so added behavior cannot disappear from
the measurement. Hooks record no timings and leave native calls in place.
"""

import re


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError("Render details boundary changed: " + before[:80])
    return source.replace(before, after)


def _reason(function, following):
    named = {
        "TextureCacheClear": "CacheClear",
        "TextureCacheDelete": "CacheDelete",
        "GetCurrentRenderingAPI": "ExternalApi",
        "GenerateCC": "Combiner",
        "gfx_set_fb_handler_custom": "FramebufferSet",
        "gfx_reset_fb_handler_custom": "FramebufferReset",
        "gfx_copy_fb_handler_custom": "FramebufferCopy",
        "gfx_read_fb_handler_custom": "FramebufferRead",
        "gfx_register_blended_texture_handler_custom": "BlendedTexture",
        "gfx_set_timg_fb_handler_custom": "FramebufferTexture",
        "Run": "FrameEnd",
        "RunGuiOnly": "FrameEnd",
        "EndFrame": "FrameEnd",
        "StartFrame": "FrameEnd",
    }
    if function in named:
        return named[function]
    if function == "TextureCacheLookup":
        return (
            "TextureSelect"
            if "mRapi->SelectTexture" in following[:100]
            else "TextureMiss"
        )
    for needle, reason in (
        ("mRapi->SetDepthTestAndMask", "Depth"),
        ("mRapi->SetZmodeDecal", "Decal"),
        ("mRapi->SetViewport", "Viewport"),
        ("mRapi->SetScissor", "Scissor"),
        ("ImportTexture(", "TextureImport"),
        ("mRapi->SetSamplerParameters", "Sampler"),
        ("mRapi->UnloadShader", "Shader"),
        ("mRapi->SetUseAlpha", "Alpha"),
    ):
        if needle in following[:200]:
            return reason
    if (
        function in ("GfxSpTri1", "GfxSpTri2")
        or following.lstrip().startswith("}")
        and function == "DrawTriangle"
    ):
        return "BufferFull"
    raise ValueError("Unclassified Flush in " + function + ": " + following[:100])


def transform(source, texture_hooks=True):
    source = '#include "application/render_details.h"\n' + source
    functions = list(
        re.finditer(
            r"(?m)^(?:void|bool|ColorCombiner\*|ShaderProgram\*|GfxRenderingAPI\*)\s+([\w:]+)\(",
            source,
        )
    )
    pattern = r"(?m)^(\s*)((?:gfx->)?Flush\(\);)$"

    def annotate(match):
        owner = next(
            (
                m[1].split("::")[-1]
                for m in reversed(functions)
                if m.start() < match.start()
            ),
            "unknown",
        )
        reason = _reason(owner, source[match.end() :])
        indent = match[1]
        return (
            indent
            + "ModernFrameProfile::SetFlushReason(ModernFrameProfile::Flush"
            + reason
            + ");\n"
            + match[0]
        )

    source, count = re.subn(pattern, annotate, source)
    if source.count("Flush();") != count:
        raise ValueError("Unattributed Flush boundary")
    if "void Interpreter::Flush() {" in source:
        source = once(
            source,
            "void Interpreter::Flush() {",
            "void Interpreter::Flush() {\n"
            "    ModernFrameProfile::ObserveFlush(mBufVboLen ? mBufVboNumTris : 0);",
        )
    if not texture_hooks:
        return source
    start = source.index("bool Interpreter::TextureCacheLookup(")
    end = source.index("\n}", start) + 2
    body = source[start:end]
    body = once(
        body,
        "return true;",
        "ModernFrameProfile::ObserveTextureLookup(true);\n        return true;",
    )
    body = once(
        body,
        "return false;",
        "ModernFrameProfile::ObserveTextureLookup(false);\n    return false;",
    )
    source = source[:start] + body + source[end:]
    for signature, mask in (
        (
            "void Interpreter::ImportTexture(int i, int tile, bool importReplacement) {",
            "false",
        ),
        ("void Interpreter::ImportTextureMask(int i, int tile) {", "true"),
    ):
        source = once(
            source,
            signature,
            signature + "\n    ModernFrameProfile::ObserveTextureImport(" + mask + ");",
        )
    return source
