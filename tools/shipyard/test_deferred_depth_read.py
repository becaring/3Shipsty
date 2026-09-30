"""The environment depth read runs after an update's first replay is submitted.

It must read the depth the previous update's final replay published: the graph
callback is deferred exactly once per submission, the backend publication is
retired after that read and republished after the final replay.
"""
import unittest

from prepare_application import OUT, prepare
from prepare_game import ROOT, project_header


def ordered(test, text, *needles):
    position = -1
    for needle in needles:
        found = text.find(needle, position + 1)
        test.assertNotEqual(found, -1, needle)
        test.assertEqual(text.count(needle), 1, needle)
        position = found


class DeferredDepthReadTests(unittest.TestCase):
    def test_graph_callback_is_deferred_once(self):
        name = 'soh/src/code/graph.c'
        text, _ = project_header(name, (ROOT / name).read_bytes())
        text = text.decode()
        self.assertNotIn('gfxCtx->callback(gfxCtx, gfxCtx->callbackParam);', text)
        ordered(self, text,
                'void Graph_RunDeferredCallback(void) {',
                '    sShipyardDeferredCallback = NULL;\n    callback(sShipyardDeferredGfxCtx, sShipyardDeferredParam);',
                'void Graph_TaskSet00(GraphicsContext* gfxCtx) {',
                '    Graph_RunDeferredCallback();\n    sShipyardDeferredCallback = gfxCtx->callback;')

    def test_read_follows_first_replay_and_precedes_publication(self):
        prepare()
        source = (OUT / 'generated/soh/soh/OTRGlobals.cpp').read_text(encoding='utf-8')
        start = source.index('void RunCommands(Gfx* Commands,')
        end = source.index('extern "C" void Graph_ProcessGfxCommands(', start)
        ordered(self, source[start:end],
                '    if (mtx_replacements.size() < 2) XboxRunDeferredDepthRead(intp);',
                '        wnd->DrawAndRunGraphicsCommands(Commands, m);',
                '        if (intp->mInterpolationIndex == 0) XboxRunDeferredDepthRead(intp);',
                '        intp->mInterpolationIndex++;',
                '    XboxRunDeferredDepthRead(intp); // No replay ran this update.',
                '    intp->XboxPublishGameDepth();')
        helper = source[source.index('static void XboxRunDeferredDepthRead('):start]
        ordered(self, helper, '    Graph_RunDeferredCallback();', '    intp->XboxRetireGameDepth();')
        process = source[end:source.index('\n}\n', end)]
        ordered(self, process, 'RunCommands(commands, mtx_replacements);',
                '    Graph_RunDeferredCallback(); // RunCommands had no window.')


if __name__ == '__main__':
    unittest.main()
