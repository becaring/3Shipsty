struct AnimationContract {
    static void Inspect(WeirdAnimation value) {
        assert(!value.animationData.has_value());
        std::cout << value.GetTargetAnimation() << ':' << int(value.GetDirection()) << ':' << value.limbCount << '\n';
        for (const auto &n : value.neighborAnimations)
            std::cout << n << '\n';
#ifdef SHIPYARD_FEATURE_PROJECTED
        typedef unsigned char Byte;
#else
        typedef std::byte Byte;
#endif
        value.animationData = std::vector<Byte>(64, static_cast<Byte>(37));
        WeirdAnimation copy = value;
        assert(copy.animationData.has_value() && copy.animationData->size() == 64);
        (*value.animationData)[0] = static_cast<Byte>(91);
        assert(static_cast<unsigned char>((*copy.animationData)[0]) == 37);
        copy.animationData.reset();
        assert(!copy.animationData.has_value() && value.animationData->size() == 64);
    }
};
int main() {
    assert(weirdAnimations.size() == 5);
    for (const auto &a : weirdAnimations)
        AnimationContract::Inspect(a);
    std::cout << "Five actual restoration animations retain defaults, neighbors and copy ownership.\n";
}
