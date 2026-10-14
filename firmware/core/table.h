/* One-dimensional calibration table: linear between points, held flat
 * beyond the first and last. x must be ascending. */
#ifndef TABLE_H
#define TABLE_H

static inline float table_lookup(const float *x, const float *y, int n, float v)
{
    if (v <= x[0])
        return y[0];
    for (int i = 1; i < n; i++)
        if (v < x[i])
            return y[i - 1] + (y[i] - y[i - 1]) * (v - x[i - 1]) / (x[i] - x[i - 1]);
    return y[n - 1];
}

#endif
