  // Modern fmt's shortest round-trip branch. Integer Dragonbox digits are
  // rendered according to fmt12's fixed/exponential threshold and padding.
  if (spec.type() == 0 && spec.precision() < 0) {
    bool negative = internal::FPUtil::isnegative(static_cast<double>(value));
    char sign = negative ? '-' : spec.flag(SIGN_FLAG) ? (spec.flag(PLUS_FLAG) ? '+' : ' ') : 0;
    std::string text;
    bool finite = !internal::FPUtil::isnotanumber(value) && !internal::FPUtil::isinfinity(value);
    if (!finite) {
      text = internal::FPUtil::isnotanumber(value) ? "nan" : "inf";
    } else {
      // Windows/Xenon long double has double storage and precision.
      typedef typename shipyard_fmt_float::select_float<T>::type Float;
      shipyard_fmt_float::dragonbox::decimal_fp<Float> dec =
          shipyard_fmt_float::dragonbox::to_decimal(static_cast<Float>(value));
      char digits[32]; unsigned count = 0;
      do { digits[count++] = static_cast<char>('0' + dec.significand % 10); dec.significand /= 10; } while (dec.significand);
      std::reverse(digits, digits + count);
      int exponent = dec.exponent + static_cast<int>(count) - 1;
      int upper = (std::numeric_limits<Float>::digits10 + 1 < 16) ? std::numeric_limits<Float>::digits10 + 1 : 16;
      if (exponent >= -4 && exponent < upper) {
        int integral = static_cast<int>(count) + dec.exponent;
        if (integral <= 0) { text = "0."; text.append(-integral, '0'); text.append(digits, count); }
        else if (integral >= static_cast<int>(count)) {
          text.assign(digits, count); text.append(integral-count, '0');
          if (spec.flag(HASH_FLAG)) text += '.';
        } else {
          text.assign(digits, integral); text += '.'; text.append(digits+integral, count-integral);
        }
      } else {
        text.assign(digits, 1);
        if (count > 1 || spec.flag(HASH_FLAG)) text += '.';
        text.append(digits+1, count-1);
        text += 'e'; text += exponent < 0 ? '-' : '+';
        unsigned e = exponent < 0 ? -exponent : exponent;
        char ebuf[4]; unsigned n=0;
        do { ebuf[n++] = static_cast<char>('0'+e%10); e/=10; } while(e);
        if (n < 2) ebuf[n++]='0';
        while(n) text += ebuf[--n];
      }
    }
    if (sign) text.insert(text.begin(), sign);
    unsigned padding = spec.width() > text.size() ? static_cast<unsigned>(spec.width()-text.size()) : 0;
    Char fill = internal::CharTraits<Char>::cast(spec.fill());
    if (!finite && spec.align() == ALIGN_NUMERIC) fill = ' ';
    unsigned left = (spec.align() == ALIGN_LEFT || (!finite && spec.align() == ALIGN_DEFAULT)) ? 0 : spec.align() == ALIGN_CENTER ? padding/2 : padding;
    CharPtr dest = grow_buffer(text.size()+padding);
    unsigned pos=0;
    if (finite && spec.align()==ALIGN_NUMERIC && sign) { dest[pos++]=sign; text.erase(text.begin()); }
    for (unsigned i=0;i<left;++i) dest[pos++]=fill;
    for (unsigned i=0;i<text.size();++i) dest[pos++]=internal::CharTraits<Char>::cast(text[i]);
    for (unsigned i=left;i<padding;++i) dest[pos++]=fill;
    return;
  }
