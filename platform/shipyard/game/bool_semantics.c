/* Both native C11 and projected XDK C compile this same behavioral corpus. */
typedef struct Flags { _Bool enabled; } Flags;
_Bool return_int(int value) { return value; }
_Bool return_float(double value) { return value; }
int accept(_Bool value) { return value; }
int invoke(int value) { return accept(value); }
void store(_Bool* target, int value) { *target = value; }
int pointer_store(int value) { _Bool local = 0; store(&local, value); return local; }
int pointer_index(int value) { _Bool local = 0; _Bool* p=&local; p[0]=value; return local; }
int pointer_advance(int value) { _Bool local = 0; _Bool* p=&local; *p++=value; return local; }
int field_store(int value) { Flags flags; flags.enabled = value; return flags.enabled; }
int cast_value(int value) { return (_Bool)value; }
int initializer(int value) { _Bool local = value; return local; }
int compound_or(int value) { _Bool local = 0; local |= value; return local; }
int compound_or_true(int value) { _Bool local = 1; local |= value; return local; }
int compound_or_effect(int value) { _Bool local = 0; local |= value++; return local * 1000 + value; }
int side_effect(int value) { _Bool local = value++; return local * 1000 + value; }
int shadow(int value) {
    _Bool local = value;
    { int local = 256; local += value; if (local == 0) return 2; }
    return local;
}
int loop_scope(int value) {
    int sum = 0;
    for (int i = 0; i < 3; ++i) {
        sum += i;
        int later = value;
        sum += later;
    }
    return sum;
}
int case_scope(int value) {
    switch (value) {
        case 0:
            value = 2;
            int later = value;
        case 1:
            if (value == 2) return later;
            return 7;
        default:
            return 0;
    }
}
