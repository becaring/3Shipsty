"""Host/native contracts for the exact-key replay census and its projection."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from deferred_lit_fog import HEADER_TYPES, transform as deferred
from vertex_reuse_census import CAPTURE, CORE, transform


CONTRACT = r'''
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#define MAX_LIGHTS 32
union F3DVtx { unsigned char bytes[16]; };
/* DEFERRED TYPES */
/* CORE */
/* CAPTURE */
extern "C" {
unsigned gVertexReuseContractChecks, gVertexReuseContractSignature, gVertexReuseContractFailure;
}
static unsigned char source[1024];
static uint32_t matrix[16], attributes[200];
#define CHECK(c) do { ++gVertexReuseContractChecks; if (!(c)) return __LINE__; } while (0)
static void Inputs() {
    memset(source, 0, sizeof(source));
    memset(matrix, 0, sizeof(matrix));
    memset(attributes, 0, sizeof(attributes));
    matrix[0] = matrix[5] = matrix[10] = matrix[15] = 0x3f800000;
}
static void Begin() {
    gModernVertexReuseCensus.request = 1;
    ModernVertexReuseBeginBatch(3);
    ModernVertexReuseBeginReplay(0);
}
static void Record(unsigned tag = 0x1000, unsigned vertices = 2, unsigned attrBytes = 56) {
    ModernVertexReuseRecord(tag, vertices, source, matrix, attributes, attrBytes);
}
static void Signature() {
    const ModernVertexReuseCensus& c = gModernVertexReuseCensus;
    const unsigned values[] = { c.arenaBytes, c.entryCount, c.arenaOverflow, c.probeOverflow,
        c.replay[1].eligibleLoads, c.replay[1].fullHitLoads, c.replay[1].matrixOnlyMissLoads,
        c.replay[1].matrixOneUlpMissLoads, c.replay[1].matrixLargerMissLoads,
        c.replay[1].attributeSourceMissLoads, c.replay[1].firstSeenLoads };
    for (unsigned i = 0; i < sizeof(values) / sizeof(values[0]); ++i)
        gVertexReuseContractSignature = (gVertexReuseContractSignature ^ values[i]) * 16777619u;
}
static unsigned Contract() {
    ModernVertexReuseCensus& c = gModernVertexReuseCensus;
    Inputs();
    c.request = 0;
    ModernVertexReuseBeginBatch(3);
    Record();
    CHECK(!c.active && !c.arenaBytes && !c.entryCount);
    Begin();
    CHECK(c.active && !c.request && !c.complete && c.captureSerial == 1);
    Record(); Record();
    CHECK(c.entryCount == 1 && c.replay[0].eligibleLoads == 2 && c.replay[0].fullHitLoads == 0);
    CHECK(c.replay[0].firstSeenLoads == 2 && c.replay[0].eligibleVertices == 4);
    ModernVertexReuseBeginReplay(1);
    Record();
    CHECK(c.replay[1].fullHitLoads == 1 && c.replay[1].fullHitVertices == 2);
    ModernVertexReuseBeginReplay(2);
    Record();
    CHECK(c.replay[2].fullHitLoads == 1);
    ModernVertexReuseEndBatch();
    CHECK(c.complete && !c.active);
    const unsigned savedBytes = c.arenaBytes;
    ModernVertexReuseBeginBatch(3);
    Record();
    CHECK(c.complete && !c.active && c.arenaBytes == savedBytes);
    Signature();

    // Every matrix bit and every source/attribute byte can independently veto a hit.
    for (unsigned word = 0; word < 16; ++word) for (unsigned bit = 0; bit < 32; ++bit) {
        Inputs(); Begin(); Record();
        matrix[word] ^= 1u << bit;
        ModernVertexReuseBeginReplay(1); Record();
        CHECK(c.replay[1].fullHitLoads == 0 && c.replay[1].matrixOnlyMissLoads == 1);
        CHECK(c.replay[1].matrixOneUlpMissLoads + c.replay[1].matrixLargerMissLoads == 1);
        Signature();
    }
    for (unsigned byte = 0; byte < 32; ++byte) for (unsigned bit = 0; bit < 8; ++bit) {
        Inputs(); Begin(); Record(); source[byte] ^= 1u << bit;
        ModernVertexReuseBeginReplay(1); Record();
        CHECK(c.replay[1].fullHitLoads == 0 && c.replay[1].attributeSourceMissLoads == 1);
        Signature();
    }
    for (unsigned word = 0; word < 14; ++word) for (unsigned bit = 0; bit < 32; ++bit) {
        Inputs(); Begin(); Record(); attributes[word] ^= 1u << bit;
        ModernVertexReuseBeginReplay(1); Record();
        CHECK(c.replay[1].fullHitLoads == 0 && c.replay[1].attributeSourceMissLoads == 1);
        Signature();
    }

    Inputs(); Begin(); Record(); ++matrix[0];
    ModernVertexReuseBeginReplay(1); Record();
    CHECK(c.replay[1].matrixOneUlpMissLoads == 1 && c.replay[1].matrixOnlyMissVertices == 2);
    ModernVertexReuseBeginReplay(2); Record();
    CHECK(c.replay[2].fullHitLoads == 1); // A prior replay's new exact key is reusable.
    Inputs(); Begin(); Record(); matrix[0] += 2;
    ModernVertexReuseBeginReplay(1); Record();
    CHECK(c.replay[1].matrixLargerMissLoads == 1);
    Inputs(); Begin(); Record(); matrix[1] = 0x80000000u;
    ModernVertexReuseBeginReplay(1); Record();
    CHECK(c.replay[1].fullHitLoads == 0 && c.replay[1].matrixOneUlpMissLoads == 1);
    Inputs(); matrix[0] = 0x7f7fffffu; Begin(); Record(); matrix[0] = 0x7f800000u;
    ModernVertexReuseBeginReplay(1); Record();
    CHECK(c.replay[1].matrixLargerMissLoads == 1);
    Inputs(); matrix[0] = 0x7fc00001u; Begin(); Record(); matrix[0] = 0x7fc00002u;
    ModernVertexReuseBeginReplay(1); Record();
    CHECK(c.replay[1].matrixLargerMissLoads == 1 && c.replay[1].fullHitLoads == 0);
    Signature();

    // Distinct addresses deliberately collide; neither the bucket nor its head certifies a hit.
    Inputs(); Begin(); Record(0x1000); source[0] = 3; Record(0x11000);
    CHECK(ModernVertexReuseBucket(0x1000) == ModernVertexReuseBucket(0x11000));
    ModernVertexReuseBeginReplay(1); Record(0x1000);
    CHECK(c.replay[1].fullHitLoads == 0 && c.replay[1].attributeSourceMissLoads == 1);
    source[0] = 0; Record(0x1000);
    CHECK(c.replay[1].fullHitLoads == 1);
    source[0] = 3; Record(0x11000);
    CHECK(c.replay[1].fullHitLoads == 2);
    Record(0x21000);
    CHECK(c.replay[1].firstSeenLoads == 1);
    Signature();

    // Full-key search checks all matching source candidates, regardless of load order.
    Inputs(); Begin(); Record(); matrix[0] += 20; Record(); matrix[0] += 20; Record();
    ModernVertexReuseBeginReplay(1); matrix[0] = 0x3f800001u; Record();
    CHECK(c.replay[1].matrixOneUlpMissLoads == 1);
    matrix[0] = 0x3f800000u; Record();
    CHECK(c.replay[1].fullHitLoads == 1);
    Record(0x1000, 3);
    CHECK(c.replay[1].attributeSourceMissLoads == 1);
    Signature();

    Inputs(); Begin(); Record(0x1000, 64, 800);
    attributes[199] = 1;
    ModernVertexReuseBeginReplay(1); Record(0x1000, 64, 800);
    CHECK(c.replay[1].attributeSourceMissLoads == 1 && c.replay[1].attributeSourceMissVertices == 64);
    Signature();

    // Arena capacity and collision-chain bounds report uncertainty instead of inventing hits.
    Inputs(); Begin();
    for (unsigned i = 0; i < 600; ++i) Record(0x1000 + i * 16, 64, 800);
    CHECK(c.arenaBytes <= ModernVertexReuseArenaSize && c.arenaOverflow > 0);
    CHECK(c.entryCount == ModernVertexReuseArenaSize / (24 + 64 + 800 + 1024));
    CHECK(c.replay[0].capacityMissLoads == c.arenaOverflow);
    ModernVertexReuseBeginReplay(1); Record(0x1000, 64, 800);
    CHECK(c.replay[1].fullHitLoads == 1);
    Record(0x1000 + 599 * 16, 64, 800);
    CHECK(c.replay[1].fullHitLoads == 1 && c.replay[1].capacityMissLoads == 1);
    Signature();
    Inputs(); Begin();
    for (unsigned i = 0; i < 66; ++i) Record(0x1000 + i * 0x10000);
    CHECK(c.entryCount == 65 && c.probeOverflow == 1);
    ModernVertexReuseBeginReplay(1); Record(0x1000);
    CHECK(c.replay[1].fullHitLoads == 0 && c.replay[1].capacityMissLoads == 1);
    Signature();

    Inputs(); Begin(); Record(0x1000, 0); Record(0x1000, 65); Record(0x1000, 2, 804);
    Record(0x1000, 2, 55);
    ModernVertexReuseBeginReplay(8); Record();
    CHECK(c.rejectedInputs == 5 && c.entryCount == 0);
    ModernVertexReuseEndBatch();

    // Exercise the production snapshot serializer, not just synthetic key bytes.
    for (unsigned change = 0; change < 15; ++change) {
        Inputs(); Begin();
        XboxDeferredContext context;
        memset(&context, 0, sizeof(context));
        context.count = 1; context.scaleS = 32769; context.scaleT = 65535;
        context.nearest = context.floatLighting = true;
        ModernVertexReuseCapture(&context, reinterpret_cast<const F3DVtx*>(source), 2, matrix, false, 1280, 720);
        switch (change) {
        case 0: ++context.count; break;
        case 1: ++context.scaleS; break;
        case 2: --context.scaleT; break;
        case 3: context.fogMul = 1.0f; break;
        case 4: context.fogOffset = 1.0f; break;
        case 5: context.ambient[0] = 1; break;
        case 6: context.ambient[1] = 1; break;
        case 7: context.ambient[2] = 1; break;
        case 8: context.lights[0].coeff[0] = 1.0f; break;
        case 9: context.lights[0].coeff[1] = 1.0f; break;
        case 10: context.lights[0].coeff[2] = 1.0f; break;
        case 11: context.lights[0].color[0] = 1.0f; break;
        case 12: context.lights[0].color[1] = 1.0f; break;
        case 13: context.lights[0].color[2] = 1.0f; break;
        case 14: context.floatLighting = false; break;
        }
        ModernVertexReuseBeginReplay(1);
        ModernVertexReuseCapture(&context, reinterpret_cast<const F3DVtx*>(source), 2, matrix, false, 1280, 720);
        CHECK(c.replay[1].attributeSourceMissLoads == 1 && c.replay[1].fullHitLoads == 0);
        Signature();
    }
    XboxDeferredContext context;
    memset(&context, 0, sizeof(context)); context.count = 1;
    Inputs(); Begin();
    ModernVertexReuseCapture(&context, reinterpret_cast<const F3DVtx*>(source), 2, matrix, false, 1280, 720);
    ModernVertexReuseBeginReplay(1);
    ModernVertexReuseCapture(&context, reinterpret_cast<const F3DVtx*>(source), 2, matrix, false, 2560, 1440);
    CHECK(c.replay[1].fullHitLoads == 1); // Only the effective aspect enters the key.
    ModernVertexReuseCapture(&context, reinterpret_cast<const F3DVtx*>(source), 2, matrix, false, 1281, 720);
    ModernVertexReuseCapture(&context, reinterpret_cast<const F3DVtx*>(source), 2, matrix, true, 1280, 720);
    CHECK(c.replay[1].attributeSourceMissLoads == 2);
    Signature();
    Inputs(); Begin();
    ModernVertexReuseCapture(&context, reinterpret_cast<const F3DVtx*>(source), 2, matrix, true, 1280, 720);
    ModernVertexReuseBeginReplay(1); context.lights[31].coeff[0] = 1.0f;
    context.normalKey = 23; context.references = 7;
    ModernVertexReuseCapture(&context, reinterpret_cast<const F3DVtx*>(source), 2, matrix, true, 0, 0);
    CHECK(c.replay[1].fullHitLoads == 1); // Inactive lights, bookkeeping, and inactive aspect do not matter.
    Signature();
    Begin(); CHECK(c.arenaBytes == 0 && c.entryCount == 0 && c.probeOverflow == 0);
    ModernVertexReuseEndBatch();
    return 0;
}
extern "C" unsigned RunVertexReuseCensusContract() {
    gVertexReuseContractChecks = 0;
    gVertexReuseContractSignature = 2166136261u;
    gVertexReuseContractFailure = Contract();
    return gVertexReuseContractFailure;
}
#ifndef MODERN_VERTEX_REUSE_CONTRACT_NO_MAIN
int main() {
    const unsigned failure = RunVertexReuseCensusContract();
    printf("vertex reuse census: checks=%u signature=%08x failure=%u\n",
           gVertexReuseContractChecks, gVertexReuseContractSignature, failure);
    printf("layout: counts=%u replay=%u buckets=%u arena=%u total=%u\n",
           (unsigned)sizeof(ModernVertexReuseCounts), (unsigned)offsetof(ModernVertexReuseCensus, replay),
           (unsigned)offsetof(ModernVertexReuseCensus, buckets), (unsigned)offsetof(ModernVertexReuseCensus, arena),
           (unsigned)sizeof(ModernVertexReuseCensus));
    return failure ? 1 : 0;
}
#endif
'''


def contract_source():
    return CONTRACT.replace('/* CORE */', CORE).replace('/* DEFERRED TYPES */', HEADER_TYPES).replace(
        '/* CAPTURE */', CAPTURE)


class VertexReuseCensusTests(unittest.TestCase):
    def test_projection_is_idempotent_and_captures_completed_load_state(self):
        source = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
        projected = deferred(source)
        self.assertEqual(projected, transform(projected))
        function = projected.split('bool Interpreter::XboxTryDeferVertices(', 1)[1].split(
            'void Interpreter::XboxMaterializeVertex(', 1)[0]
        self.assertLess(function.index('GfxSpVertexEager(n_vertices, dest_index, vertices);'),
                        function.index('ModernVertexReuseCapture('))
        self.assertLess(function.index('ModernVertexReuseCapture('), function.index('pending.source = vertices[i];'))
        self.assertIn('gModernVertexReuseCensus.active && context->nearest', function)
        self.assertNotIn('attributes[', function)
        self.assertIn('static __declspec(noinline) void ModernVertexReuseCapture', projected)

    def test_host_exact_key_contract(self):
        sys.path.insert(0, str(ROOT / 'tools/shipyard/tests'))
        from test_binary import host_environment
        output = ROOT / 'scratch/vertex-reuse-census'
        output.mkdir(parents=True, exist_ok=True)
        cpp, exe = output / 'contract.cpp', output / 'contract.exe'
        cpp.write_text(contract_source())
        compiler, env = host_environment()
        compiled = subprocess.run([str(compiler), '/nologo', '/O2', '/EHsc', str(cpp),
                                   '/Fe:' + str(exe), '/Fo:' + str(output) + '/'],
                                  env=env, capture_output=True, text=True)
        self.assertEqual(0, compiled.returncode, compiled.stdout + compiled.stderr)
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        print(result.stdout.strip())
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
