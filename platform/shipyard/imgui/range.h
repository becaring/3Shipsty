#pragma once
#include <stddef.h>
// The actual ImVector iterator API and ordinary C arrays; no ownership changes.
template <class T> inline typename T::iterator ShipyardImGuiBegin(T& value) { return value.begin(); }
template <class T> inline typename T::iterator ShipyardImGuiEnd(T& value) { return value.end(); }
template <class T> inline typename T::const_iterator ShipyardImGuiBegin(const T& value) { return value.begin(); }
template <class T> inline typename T::const_iterator ShipyardImGuiEnd(const T& value) { return value.end(); }
template <class T, size_t N> inline T* ShipyardImGuiBegin(T (&value)[N]) { return value; }
template <class T, size_t N> inline T* ShipyardImGuiEnd(T (&value)[N]) { return value + N; }
