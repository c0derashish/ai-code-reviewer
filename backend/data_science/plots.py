import matplotlib

matplotlib.use("Agg")  # draw into files only. No window is needed

import matplotlib.pyplot as plt  # noqa: E402  (must come after matplotlib.use)
import pandas as pd  # noqa: E402


def _save(figure, path):
    figure.tight_layout()
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return path


def plot_histograms(table, features, path, columns=4):
    """One small histogram per feature."""
    rows = max(1, -(-len(features) // columns))  # round up
    figure, axes = plt.subplots(rows, columns, figsize=(columns * 3.2, rows * 2.6), squeeze=False)

    for index, axis in enumerate(axes.flat):
        if index >= len(features):
            axis.axis("off")
            continue

        name = features[index]
        values = pd.to_numeric(table[name], errors="coerce").dropna()
        axis.set_title(f"{name} (n={len(values)})", fontsize=8)
        axis.tick_params(labelsize=7)
        if len(values) == 0:
            axis.text(0.5, 0.5, "no data", ha="center", va="center", transform=axis.transAxes)
        else:
            axis.hist(values, bins=20)

    return _save(figure, path)


def plot_correlation_heatmap(table, features, path):
    """Spearman correlations between features. Only for looking, not for proof."""
    data = table[features].apply(pd.to_numeric, errors="coerce")
    matrix = data.corr(method="spearman", min_periods=3).to_numpy(dtype=float)

    size = max(5, len(features) * 0.55)
    figure, axis = plt.subplots(figsize=(size + 1, size))
    image = axis.imshow(matrix, vmin=-1, vmax=1, cmap="coolwarm")

    axis.set_xticks(range(len(features)))
    axis.set_xticklabels(features, rotation=90, fontsize=8)
    axis.set_yticks(range(len(features)))
    axis.set_yticklabels(features, fontsize=8)

    for i in range(len(features)):
        for j in range(len(features)):
            if matrix[i, j] == matrix[i, j]:  # not NaN
                axis.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=6)

    figure.colorbar(image, ax=axis, shrink=0.8)
    axis.set_title("Spearman correlation")
    return _save(figure, path)


def plot_top_rules(rules, path, top=15):
    """Bar chart of the most frequent findings."""
    data = rules.head(top).iloc[::-1]
    figure, axis = plt.subplots(figsize=(8, max(3, 0.35 * len(data) + 1)))

    if data.empty:
        axis.text(0.5, 0.5, "no findings", ha="center", va="center", transform=axis.transAxes)
        axis.axis("off")
    else:
        labels = [f"{source}: {name}" for source, name in zip(data["source"], data["rule_name"])]
        axis.barh(labels, data["findings"])
        axis.set_xlabel("findings")
        axis.tick_params(labelsize=8)

    return _save(figure, path)