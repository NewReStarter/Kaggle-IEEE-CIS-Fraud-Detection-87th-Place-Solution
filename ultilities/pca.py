import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

def get_dc_feature(df_train, df_test, n_comp=12, used_features=None):
    if not used_features:
        used_features = df_test.columns

    train = df_train.copy()
    test = df_test.copy()

    # PCA
    pca = PCA(n_components=n_comp, random_state=420)
    pca2_results_train = pca.fit_transform(train[used_features])
    pca2_results_test = pca.transform(test[used_features])

    for i in range(1, n_comp + 1):
        train['pca_' + str(i)] = pca2_results_train[:, i - 1]
        test['pca_' + str(i)] = pca2_results_test[:, i - 1]

    return train, test