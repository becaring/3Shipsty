#ifndef SHIPYARD_STDBOOL_H
#define SHIPYARD_STDBOOL_H
/* C preprocessing preserves the semantic type for the compiler projection.
 * It must never be replaced by an unsigned-char typedef: conversion to bool
 * canonicalizes arbitrary nonzero values, including 256 and negative values. */
#ifndef __cplusplus
#define bool _Bool
#define true 1
#define false 0
#endif
#define __bool_true_false_are_defined 1
#endif
