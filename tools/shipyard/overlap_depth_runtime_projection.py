"""Sample single-replay depth after the frame's command walk, not before it.

The sample reads the previous update's published depth either way, and the
game applies it two builds later, so values and timing do not change. Locking
it before the walk made the CPU wait for the GPU to drain and left the GPU idle
while the frame was recorded; resolves meanwhile take the spare depth storage.
"""


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Expected one depth anchor: " + old)
    return text.replace(old, new)


def runtime(text):
    text = once(text, """\
    if (packet.replay.maps.size() < 2) {
        Shipyard_OverlapSampleDepth(&packet.depth, &depth, PrepareDepth, ReadDepth, NULL);
        interpreter->XboxRetireGameDepth();
        sampled = true;
    }
""", "")
    text = once(text, """\
            if (index == 0) {
                if (!sampled) {""", """\
            if (index == 0 && packet.replay.maps.size() > 1) {
                if (!sampled) {""")
    return once(text, """\
    interpreter->XboxRetireGameDepth();
    interpreter->XboxPublishGameDepth();
    handoff.Submit();""", """\
    if (!sampled) Shipyard_OverlapSampleDepth(&packet.depth, &depth, PrepareDepth, ReadDepth, NULL);
    interpreter->XboxRetireGameDepth();
    interpreter->XboxPublishGameDepth();
    handoff.Submit();""")
