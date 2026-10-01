"""의사결정나무 -> 사람이 읽는 규칙표(조건, 표본수, 이벤트율/평균값)."""
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


def tree_rules(tree, feat_names, X, y, w=None):
    t = tree.tree_
    leaves = tree.apply(X)
    w = np.ones(len(y)) if w is None else np.asarray(w)
    paths = {}

    def rec(node, conds):
        if t.children_left[node] == -1:
            paths[node] = conds
            return
        f, th = feat_names[t.feature[node]], t.threshold[node]
        rec(t.children_left[node], conds + [f"{f} <= {th:.1f}"])
        rec(t.children_right[node], conds + [f"{f} > {th:.1f}"])

    rec(0, [])
    rows = []
    y = np.asarray(y, float)
    for leaf, conds in paths.items():
        m = leaves == leaf
        rows.append({"조건": " & ".join(conds), "표본수": int(m.sum()),
                     "가중평균": float(np.sum(y[m] * w[m]) / np.sum(w[m])) if m.any() else np.nan})
    return pd.DataFrame(rows).sort_values("가중평균", ascending=False).reset_index(drop=True)


def fit_rules(X, y, feats, names, w=None, depth=3, min_leaf=150, classifier=True):
    Est = DecisionTreeClassifier if classifier else DecisionTreeRegressor
    tr = Est(max_depth=depth, min_samples_leaf=min_leaf, random_state=0)
    tr.fit(X[feats], y, sample_weight=w)
    return tree_rules(tr, names, X[feats], y, w)
