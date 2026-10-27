"""Borrow controller map entries during polling without changing call order.

Mapping callbacks do not edit their owning maps. The comparator uses the map's
const-key value_type so binding a reference cannot create a converting pair.
"""
import re

from source_anchor import replace_once


def project(relative, source):
    if relative == 'src/libultraship/controller/controldevice/controller/Controller.cpp':
        raw = 'for (auto [bitmask, button] : mButtons)'
        if raw in source:
            return replace_once(source, raw, 'for (const auto& [bitmask, button] : mButtons)')
        signature = 'void Controller::ReadToOSContPad('
        start = source.index(signature)
        end = source.index('// Stick Inputs', start)
        part, count = re.subn(r'auto (_controllerPair\d+) = (\*_configIt\d+);',
                             r'const auto& \1 = \2;', source[start:end])
        if count != 1:
            raise ValueError('Controller polling loop anchor drift')
        return source[:start] + part + source[end:]
    if relative == 'src/ship/controller/controldevice/controller/ControllerStick.cpp':
        for name in ('a', 'b'):
            source = replace_once(source,
                'const std::pair<std::string, std::shared_ptr<ControllerAxisDirectionMapping>> ' + name,
                'const std::unordered_map<std::string, std::shared_ptr<ControllerAxisDirectionMapping> >::value_type& ' + name)
    return source
