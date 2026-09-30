// Included after the complete pure math/record methods extracted for this host
// audit. The full production TU is compiled separately by XDK; no fake matrix,
// game or OTR service is supplied in either path.
#include <cassert>
#include <cstdio>
#include <cstring>
static unsigned long long resultHash = 1469598103934665603ULL;
static void hashBytes(const void *data, size_t length) {
    const unsigned char *p = (const unsigned char *)data;
    while (length--) {
        resultHash ^= *p++;
        resultHash *= 1099511628211ULL;
    }
}
int main() {
    static_assert(sizeof(Data) == sizeof(MtxF) + sizeof(Mtx *) + 8, "Original record union layout on 64-bit host");
    char keys[8];
    for (int a = 0; a < 8; ++a)
        for (int b = 0; b < 8; ++b)
            for (int i = -2; i < 3; ++i)
                for (int j = -2; j < 3; ++j) {
                    label x = {keys + a, i}, y = {keys + b, j};
                    std::pair<const void *, int> px(keys + a, i), py(keys + b, j);
                    assert((x < y) == (px < py));
                }
    unsigned angleCount = 0;
    InterpolateCtx ctx;
    MtxF oldMatrix, newMatrix, mixed;
    for (int i = 0; i < 16; ++i) {
        oldMatrix.mf[i / 4][i % 4] = (i - 7) * 3.0f;
        newMatrix.mf[i / 4][i % 4] = (i - 5) * -7.0f;
    }
    for (int step = 0; step <= 8; ++step) {
        ctx.step = step / 8.f;
        ctx.w = 1.f - ctx.step;
        ctx.interpolate_mtxf(&mixed, &oldMatrix, &newMatrix);
        hashBytes(&mixed, sizeof(mixed));
        for (int a = -32768; a <= 32767; a += 257)
            for (int b = -32768; b <= 32767; b += 257) {
                s16 v = ctx.interpolate_angle(static_cast<s16>(a), static_cast<s16>(b));
                hashBytes(&v, sizeof(v));
                ++angleCount;
            }
        for (int a = -40; a <= 40; ++a)
            for (int b = -40; b <= 40; ++b) {
                float v = ctx.interpolate_angle(a / 4.f, b / 4.f);
                hashBytes(&v, sizeof(v));
            }
    }
    float identity[16] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1}, inverse[16], singular[16] = {0};
    assert(invert_matrix(identity, inverse));
    assert(memcmp(identity, inverse, sizeof(identity)) == 0);
    assert(!invert_matrix(singular, inverse));
    for (int i = 1; i <= 32; ++i) {
        identity[0] = i;
        identity[5] = i + 1;
        identity[10] = i + 2;
        identity[12] = i / 3.f;
        assert(invert_matrix(identity, inverse));
        hashBytes(inverse, sizeof(inverse));
    }
    current_recording = Recording();
    current_path.clear();
    current_path.push_back(&current_recording.root_path);
    is_recording = true;
    FrameInterpolation_RecordOpenChild(keys + 1, 7);
    FrameInterpolation_RecordMatrixPush();
    FrameInterpolation_RecordMatrixPut(&oldMatrix);
    FrameInterpolation_RecordMatrixMult(&newMatrix, 1);
    FrameInterpolation_RecordMatrixTranslate(1, 2, 3, 1);
    FrameInterpolation_RecordMatrixScale(4, 5, 6, 0);
    FrameInterpolation_RecordMatrixRotate1Coord(2, 1.25f, 1);
    FrameInterpolation_RecordMatrixRotateZYX(-123, 456, -789, 0);
    Vec3f pos = {1.25f, -2.5f, 3.75f};
    Vec3s rot = {-7, 8, -9};
    FrameInterpolation_RecordMatrixTranslateRotateZYX(&pos, &rot);
    Mtx destination;
    FrameInterpolation_RecordMatrixMtxFToMtx(&oldMatrix, &destination);
    FrameInterpolation_RecordMatrixReplaceRotation(&newMatrix);
    FrameInterpolation_RecordMatrixRotateAxis(1.5f, &pos, 1);
    FrameInterpolation_RecordMatrixPop();
    auto p = current_path.back();
    assert(p->items.size() == 12);
    assert(p->ops[Op::MatrixPut][0].matrix_put.src.xx == oldMatrix.xx);
    assert(p->ops[Op::MatrixMult][0].matrix_mult.mode == 1);
    assert(p->ops[Op::MatrixTranslate][0].matrix_translate.z == 3);
    assert(p->ops[Op::MatrixScale][0].matrix_scale.y == 5);
    assert(p->ops[Op::MatrixRotate1Coord][0].matrix_rotate_1_coord.value == 1.25f);
    assert(p->ops[Op::MatrixRotateZYX][0].matrix_rotate_zyx.x == -123);
    assert(p->ops[Op::MatrixTranslateRotateZYX][0].matrix_translate_rotate_zyx.rotation.z == -9);
    assert(p->ops[Op::MatrixMtxFToMtx][0].matrix_mtxf_to_mtx.dest == &destination);
    assert(p->ops[Op::MatrixReplaceRotation][0].matrix_replace_rotation.mf.xy == newMatrix.xy);
    assert(p->ops[Op::MatrixRotateAxis][0].matrix_rotate_axis.angle == 1.5f);
    FrameInterpolation_RecordCloseChild();
    assert(current_path.size() == 1);
    previous_camera_epoch = 5;
    FrameInterpolation_DontInterpolateCamera();
    assert(FrameInterpolation_GetCameraEpoch() == 6);
    FrameInterpolation_StopRecord();
    assert(!is_recording && previous_camera_epoch == 6);
    FrameInterpolation_RecordMatrixPop();
    assert(current_recording.root_path.ops.size() == 1 && current_recording.root_path.ops.count(Op::OpenChild) == 1);
    printf("%u integer-angle cases, float/matrix interpolation, inverses, record payloads/lifecycle, label ordering; "
           "hash %llu\n",
           angleCount, resultHash);
}
