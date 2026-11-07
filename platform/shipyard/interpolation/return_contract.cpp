#include <cassert>
#include <cstdio>
#include <unordered_map>
#include <utility>

// Only map production is substituted: execute the extracted return function
// against unordered_map storage and instrument each 4x4 payload copy.
struct Mtx {};
struct MtxF {
    float values[4][4];
    static unsigned copies;
    MtxF() : values() {}
    MtxF(const MtxF& other) {
        ++copies;
        for (unsigned i = 0; i < 4; ++i)
            for (unsigned j = 0; j < 4; ++j)
                values[i][j] = other.values[i][j];
    }
};
unsigned MtxF::copies = 0;
using std::unordered_map;
static Mtx keys[1024];
static unsigned count;
struct Recording { int root_path; } previous_recording, current_recording;
struct InterpolateCtx {
    float step, w;
    unordered_map<Mtx*, MtxF> mtx_replacements;
    void interpolate_branch(int*, int*) {
        for (unsigned i = 0; i < count; ++i) {
            MtxF& matrix = mtx_replacements[&keys[i]];
            for (unsigned row = 0; row < 4; ++row)
                for (unsigned col = 0; col < 4; ++col)
                    matrix.values[row][col] = float(i * 16 + row * 4 + col) + step;
        }
        MtxF::copies = 0;
    }
};

// EXTRACTED_ENTRY

int main() {
    const unsigned sizes[] = {0, 1, 64, 1024};
    for (unsigned n : sizes) {
        count = n;
        auto first = FrameInterpolation_Interpolate(0.25f);
        const unsigned firstCopies = MtxF::copies;
        auto second = FrameInterpolation_Interpolate(0.75f);
        assert(first.size() == n && second.size() == n);
        for (unsigned i = 0; i < n; ++i) {
            for (unsigned row = 0; row < 4; ++row) {
                for (unsigned col = 0; col < 4; ++col) {
                    const float value = float(i * 16 + row * 4 + col);
                    assert(first.at(&keys[i]).values[row][col] == value + 0.25f);
                    assert(second.at(&keys[i]).values[row][col] == value + 0.75f);
                }
            }
        }
        std::printf("entries=%u copies=%u repeated=%u\n", n, firstCopies, MtxF::copies);
        assert(firstCopies == EXPECTED_COPY_FACTOR * n);
        assert(MtxF::copies == EXPECTED_COPY_FACTOR * n);
    }
}
