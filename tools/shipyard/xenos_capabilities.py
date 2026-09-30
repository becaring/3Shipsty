"""Capabilities of this consumer's Fast3D and framebuffer adapters."""

import os


def compiler_options():
    diagnostics = os.environ.get('SHIPYARD_XENOS_DIAGNOSTICS', '0')
    if diagnostics not in ('0', '1'):
        raise ValueError('SHIPYARD_XENOS_DIAGNOSTICS must be 0 or 1')
    capabilities = {
        'SHADER_ABI': '2',
        'SHADER_PACK': '1',
        'DEFERRED_FRAMEBUFFERS': '1',
        'BINDING_REUSE': '1',
        'TILING_BUDGET': '1',
        'ALPHA_HISTOGRAM': '1',
        'DIAGNOSTICS': diagnostics,
    }
    return ['/DSHIPYARD_XENOS_' + name + '=' + value
            for name, value in capabilities.items()]
