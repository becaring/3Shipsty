"""Remove discarded matrix calculations from prepared interpolation replay.

Recorded output matrices do not read the replay stack. A balanced push/pop
region without an actor-matrix capture can omit its stack calculations while
preserving output writes, replay order, and the matrix state after the pop.
"""

from prepare_configuration import once


def transform(text):
    text = once(
        text,
        "struct InterpolateCtx {",
        r"""static bool DiscardedInterpolationStackOp(Op op) {
    switch (op.GetValue()) {
        case Op::MatrixPush:
        case Op::MatrixPop:
        case Op::MatrixPut:
        case Op::MatrixMult:
        case Op::MatrixTranslate:
        case Op::MatrixScale:
        case Op::MatrixRotate1Coord:
        case Op::MatrixRotateZYX:
        case Op::MatrixTranslateRotateZYX:
        case Op::MatrixSetTranslateRotateYXZ:
        case Op::MatrixReplaceRotation:
        case Op::MatrixRotateAxis:
            return true;
        default:
            return false;
    }
}

static void PruneDiscardedInterpolationStack() {
    if (is_recording || prepared_interpolation.empty()) return;
    const size_t count = prepared_interpolation.size();
    std::vector<std::pair<size_t, size_t>> pushes;
    std::vector<int> discarded(count + 1, 0);
    size_t captures = 0;
    bool changed = false;
    for (size_t i = 0; i < count; ++i) {
        const PreparedInterpolationEntry& entry = prepared_interpolation[i];
        if (entry.op == Op::MatrixPush) {
            pushes.push_back(std::make_pair(i, captures));
        } else if (entry.op == Op::MatrixPop) {
            if (!pushes.empty()) {
                const std::pair<size_t, size_t> push = pushes.back();
                pushes.pop_back();
                if (push.second == captures) {
                    ++discarded[push.first];
                    --discarded[i + 1];
                    changed = true;
                }
            }
        } else if (entry.op == Op::MatrixSetTranslateRotateYXZ &&
                   entry.old_op->matrix_set_translate_rotate_yxz.has_mtx &&
                   entry.new_op->matrix_set_translate_rotate_yxz.has_mtx) {
            ++captures;
        }
    }
    if (!changed) return;
    size_t kept = 0;
    int depth = 0;
    for (size_t i = 0; i < count; ++i) {
        depth += discarded[i];
        if (depth && DiscardedInterpolationStackOp(prepared_interpolation[i].op)) continue;
        if (kept != i) prepared_interpolation[kept] = prepared_interpolation[i];
        ++kept;
    }
    prepared_interpolation.resize(kept);
}

struct InterpolateCtx {""",
    )
    return once(
        text,
        "            prepare_branch(old_path, new_path);\n            prepared_interpolation_valid = true;",
        "            prepare_branch(old_path, new_path);\n"
        "            PruneDiscardedInterpolationStack();\n"
        "            prepared_interpolation_valid = true;",
    )
