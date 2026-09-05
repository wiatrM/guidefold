// Exact Guidefold dense comparator. No floating point, sqrt or approximations.
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <numeric>
#include <vector>

namespace {
constexpr std::int64_t kBound = std::int64_t{1} << 40;
constexpr std::size_t kMaxItems = 1000000;
}

extern "C" int guidefold_dense_rank_abi() noexcept { return 1; }

extern "C" int guidefold_dense_rank(
    const std::int64_t* dots, const std::int64_t* norms,
    std::size_t count, std::size_t* output) noexcept {
    if (count > kMaxItems || (count && (!dots || !norms || !output))) return 1;
    for (std::size_t i = 0; i < count; ++i) {
        // Inclusive bound gives |dot|^2 * norm <= 2^120, below signed 2^127.
        // Avoid abs(INT64_MIN): direct comparisons are always well-defined.
        if (dots[i] < -kBound || dots[i] > kBound ||
            norms[i] <= 0 || norms[i] > kBound) return 2;
    }
    try {
        std::vector<std::size_t> order(count);
        std::iota(order.begin(), order.end(), std::size_t{0});
        std::sort(order.begin(), order.end(), [&](std::size_t a, std::size_t b) {
            const __int128 da = dots[a], db = dots[b];
            __int128 lhs = da * da * static_cast<__int128>(norms[b]);
            __int128 rhs = db * db * static_cast<__int128>(norms[a]);
            if (da < 0) lhs = -lhs;
            if (db < 0) rhs = -rhs;
            if (lhs != rhs) return lhs > rhs;
            if (da != db) return da > db;
            // Python supplies indices in lexicographic URN order.
            return a < b;
        });
        std::copy(order.begin(), order.end(), output);
        return 0;
    } catch (...) {
        return 3;
    }
}