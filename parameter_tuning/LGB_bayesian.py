import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
import seaborn as sns
import datetime

from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score
from hyperopt import fmin, hp, tpe, space_eval
from sklearn.model_selection import KFold, TimeSeriesSplit
import lightgbm as lgb
from time import time
import os
from sklearn.model_selection import KFold
from bayes_opt import BayesianOptimization

import gc
import argparse

def cur_in_window(x):
    cur = x[0]
    window = x[1:]
    cnt = 0
    for item in window:
        if cur == item:
            cnt += 1
    return cnt

training_start_time = time()
ap = argparse.ArgumentParser(description='label_lgb2.py')
ap.add_argument('size', nargs='*', action="store", default=-1, type=int)
pa = ap.parse_args()
size = pa.size[0]

if size == -1:
    NROWS = None
else:
    NROWS = size
print("NROWS: ", NROWS)

test = pd.read_csv('../temp/test_label.csv', nrows=NROWS)
test = test.drop('isFraud', axis=1)
sub = pd.read_csv('../temp/sample_submission_label.csv', nrows=NROWS)

def reduce_mem_usage(df):
    start_mem = df.memory_usage().sum() / 1024 ** 2
    for col in df.columns:
        col_type = df[col].dtype

        if col_type != object:
            c_min = df[col].min()
            c_max = df[col].max()
            if str(col_type)[: 3] == 'int':
                if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                    df[col] = df[col].astype(np.int8)
                elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                    df[col] = df[col].astype(np.int16)
                elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
                elif c_min > np.iinfo(np.int64).min and c_max < np.iinfo(np.int64).max:
                    df[col] = df[col].astype(np.int64)
            else:
                if c_min > np.finfo(np.float16).min and c_max < np.finfo(np.float16).max:
                    df[col] = df[col].astype(np.float16)
                elif c_min > np.finfo(np.float32).min and c_max < np.finfo(np.float32).max:
                    df[col] = df[col].astype(np.float32)

    end_mem = df.memory_usage().sum() / 1024 ** 2
    print('Memory usage after optimization is: {:.2f} MB, {:.1f}% reduction'.format(end_mem, 100 * (
                start_mem - end_mem) / start_mem))

    return df

train = reduce_mem_usage(train)
test = reduce_mem_usage(test)

train['card_addr1_P_emaildomain'] = train["card1"].apply(lambda x: str(x)) + "_" + train["card2"].apply(
    lambda x: str(x)) + \
                                    "_" + train["card3"].apply(lambda x: str(x)) + "_" + train["card4"].apply(
    lambda x: str(x)) + \
                                    "_" + train["card5"].apply(lambda x: str(x)) + "_" + train["card6"].apply(
    lambda x: str(x)) + \
                                    "_" + train["addr1"].apply(lambda x: str(x)) + "_" + train["P_emaildomain"].apply(
    lambda x: str(x))

test['card_addr1_P_emaildomain'] = test["card1"].apply(lambda x: str(x)) + "_" + test["card2"].apply(lambda x: str(x)) + \
                                   "_" + test["card3"].apply(lambda x: str(x)) + "_" + test["card4"].apply(
    lambda x: str(x)) + \
                                   "_" + test["card5"].apply(lambda x: str(x)) + "_" + test["card6"].apply(
    lambda x: str(x)) + \
                                   "_" + test["addr1"].apply(lambda x: str(x)) + "_" + test["P_emaildomain"].apply(
    lambda x: str(x))

shift_feature = []
for i in range(1, 51):
    train["card_addr1_P_emaildomain_" + str(i) + "before"] = train["card_addr1_P_emaildomain"].shift(i)
    test["card_addr1_P_emaildomain_" + str(i) + "before"] = test["card_addr1_P_emaildomain"].shift(i)
    shift_feature.append("card_addr1_P_emaildomain_" + str(i) + "before")

for i in range(-1, -51, -1):
    train["card_addr1_P_emaildomain_" + str(-i) + "after"] = train["card_addr1_P_emaildomain"].shift(i)
    test["card_addr1_P_emaildomain_" + str(-i) + "after"] = test["card_addr1_P_emaildomain"].shift(i)
    shift_feature.append("card_addr1_P_emaildomain_" + str(-i) + "after")


train["shift_100_cnt"] = train[["card_addr1_P_emaildomain"] + shift_feature].apply(lambda x: cur_in_window(x), axis=1)
test["shift_100_cnt"] = test[["card_addr1_P_emaildomain"] + shift_feature].apply(lambda x: cur_in_window(x), axis=1)
train = train.drop(["card_addr1_P_emaildomain"] + shift_feature, axis=1)
test = test.drop(["card_addr1_P_emaildomain"] + shift_feature, axis=1)
train['null'] = train.isna().sum(axis=1)
test['null'] = test.isna().sum(axis=1)

train['TransactionAmt'] = train['TransactionAmt'].astype(float)
train['TransAmtLog'] = np.log(train['TransactionAmt'])
train['TransAmtDemical'] = train['TransactionAmt'].astype('str').str.split('.', expand=True)[1].str.len()

test['TransactionAmt'] = test['TransactionAmt'].astype(float)
test['TransAmtLog'] = np.log(test['TransactionAmt'])
test['TransAmtDemical'] = test['TransactionAmt'].astype('str').str.split('.', expand=True)[1].str.len()

def mod_m(x, m):
    if x % m == 0:
        return 1
    else:
        return 0

train['TransactionAmt_mod_1'] = train['TransactionAmt'].apply(lambda x: mod_m(x, 1))
train['TransactionAmt_mod_10'] = train['TransactionAmt'].apply(lambda x: mod_m(x, 10))
train['TransactionAmt_mod_50'] = train['TransactionAmt'].apply(lambda x: mod_m(x, 50))
train['TransactionAmt_mod_100'] = train['TransactionAmt'].apply(lambda x: mod_m(x, 100))

test['TransactionAmt_mod_1'] = test['TransactionAmt'].apply(lambda x: mod_m(x, 1))
test['TransactionAmt_mod_10'] = test['TransactionAmt'].apply(lambda x: mod_m(x, 10))
test['TransactionAmt_mod_50'] = test['TransactionAmt'].apply(lambda x: mod_m(x, 50))
test['TransactionAmt_mod_100'] = test['TransactionAmt'].apply(lambda x: mod_m(x, 100))

def get_sub(x, idx):
    try:
        return str(x)[idx]
    except:
        return "-1"

for idx in [-1, -2, -3, -4, -5]:
    train["card1" + "_sub_" + str(idx)] = train["card1"].apply(lambda x: get_sub(x, idx))
    test["card1" + "_sub_" + str(idx)] = test["card1"].apply(lambda x: get_sub(x, idx))


train["card1_len"] = train["card1"].apply(lambda x: len(str(x)))
test["card1_len"] = test["card1"].apply(lambda x: len(str(x)))

train["card1_first"] = train["card1"].apply(lambda x: str(x)[0])
test["card1_first"] = test["card1"].apply(lambda x: str(x)[0])

train["card1_na"] = 0
train.loc[train["card1"].isna(), "card1_na"] = 1
test["card1_na"] = 0
test.loc[test["card1"].isna(), "card1_na"] = 1

train["card2_na"] = 0
train.loc[train["card2"].isna(), "card2_na"] = 1
test["card2_na"] = 0
test.loc[test["card2"].isna(), "card2_na"] = 1

train["card5_na"] = 0
train.loc[train["card5"].isna(), "card5_na"] = 1
test["card5_na"] = 0
test.loc[test["card5"].isna(), "card5_na"] = 1

train['card_str'] = train["card1"].apply(lambda x: str(x)) + "_" + train["card2"].apply(lambda x: str(x)) + "_" + train[
    "card3"].apply(lambda x: str(x)) + "_" + train["card4"].apply(lambda x: str(x)) + "_" + train["card5"].apply(
    lambda x: str(x)) + "_" + train["card6"].apply(lambda x: str(x))

test['card_str'] = test["card1"].apply(lambda x: str(x)) + "_" + test["card2"].apply(lambda x: str(x)) + "_" + test[
    "card3"].apply(lambda x: str(x)) + "_" + test["card4"].apply(lambda x: str(x)) + "_" + test["card5"].apply(
    lambda x: str(x)) + "_" + test["card6"].apply(lambda x: str(x))

train['card_count_full'] = train['card_str'].map(
    pd.concat([train['card_str'], test['card_str']], ignore_index=True).value_counts(dropna=False))
test['card_count_full'] = test['card_str'].map(
    pd.concat([test['card_str'], test['card_str']], ignore_index=True).value_counts(dropna=False))

train['TransactionAmt_to_std_card_str'] = train['TransactionAmt'] / train.groupby(['card_str'])[
    'TransactionAmt'].transform('std')
test['TransactionAmt_to_std_card_str'] = test['TransactionAmt'] / test.groupby(['card_str'])[
    'TransactionAmt'].transform('std')

train['TransactionAmt_to_mean_card_str'] = train['TransactionAmt'] / train.groupby(['card_str'])[
    'TransactionAmt'].transform('mean')
test['TransactionAmt_to_mean_card_str'] = test['TransactionAmt'] / test.groupby(['card_str'])[
    'TransactionAmt'].transform('mean')

train['TransactionAmt_to_sum_card_str'] = train['TransactionAmt'] / train.groupby(['card_str'])[
    'TransactionAmt'].transform('sum')
test['TransactionAmt_to_sum_card_str'] = test['TransactionAmt'] / test.groupby(['card_str'])[
    'TransactionAmt'].transform('sum')

train['card1_count_full'] = train['card1'].map(
    pd.concat([train['card1'], test['card1']], ignore_index=True).value_counts(dropna=False))
test['card1_count_full'] = test['card1'].map(
    pd.concat([train['card1'], test['card1']], ignore_index=True).value_counts(dropna=False))

train['card2_count_full'] = train['card2'].map(
    pd.concat([train['card2'], test['card2']], ignore_index=True).value_counts(dropna=False))
test['card2_count_full'] = test['card2'].map(
    pd.concat([train['card2'], test['card2']], ignore_index=True).value_counts(dropna=False))

train['card3_count_full'] = train['card3'].map(
    pd.concat([train['card3'], test['card3']], ignore_index=True).value_counts(dropna=False))
test['card3_count_full'] = test['card3'].map(
    pd.concat([train['card3'], test['card3']], ignore_index=True).value_counts(dropna=False))

train['card4_count_full'] = train['card4'].map(
    pd.concat([train['card4'], test['card4']], ignore_index=True).value_counts(dropna=False))
test['card4_count_full'] = test['card4'].map(
    pd.concat([train['card4'], test['card4']], ignore_index=True).value_counts(dropna=False))

train['card5_count_full'] = train['card5'].map(
    pd.concat([train['card5'], test['card5']], ignore_index=True).value_counts(dropna=False))
test['card5_count_full'] = test['card5'].map(
    pd.concat([train['card5'], test['card5']], ignore_index=True).value_counts(dropna=False))

train['card6_count_full'] = train['card6'].map(
    pd.concat([train['card6'], test['card6']], ignore_index=True).value_counts(dropna=False))
test['card6_count_full'] = test['card6'].map(
    pd.concat([train['card6'], test['card6']], ignore_index=True).value_counts(dropna=False))

train['TransactionAmt_to_mean_card1'] = train['TransactionAmt'] / train.groupby(['card1'])['TransactionAmt'].transform(
    'mean')
train['TransactionAmt_to_mean_card2'] = train['TransactionAmt'] / train.groupby(['card2'])['TransactionAmt'].transform(
    'mean')
test['TransactionAmt_to_mean_card1'] = test['TransactionAmt'] / test.groupby(['card1'])['TransactionAmt'].transform(
    'mean')
test['TransactionAmt_to_mean_card2'] = test['TransactionAmt'] / test.groupby(['card2'])['TransactionAmt'].transform(
    'mean')

train['TransactionAmt_to_mean_card3'] = train['TransactionAmt'] / train.groupby(['card3'])['TransactionAmt'].transform(
    'mean')
train['TransactionAmt_to_mean_card4'] = train['TransactionAmt'] / train.groupby(['card4'])['TransactionAmt'].transform(
    'mean')
test['TransactionAmt_to_mean_card3'] = test['TransactionAmt'] / test.groupby(['card3'])['TransactionAmt'].transform(
    'mean')
test['TransactionAmt_to_mean_card4'] = test['TransactionAmt'] / test.groupby(['card4'])['TransactionAmt'].transform(
    'mean')

train['TransactionAmt_to_mean_card5'] = train['TransactionAmt'] / train.groupby(['card5'])['TransactionAmt'].transform(
    'mean')
train['TransactionAmt_to_mean_card6'] = train['TransactionAmt'] / train.groupby(['card6'])['TransactionAmt'].transform(
    'mean')
test['TransactionAmt_to_mean_card5'] = test['TransactionAmt'] / test.groupby(['card5'])['TransactionAmt'].transform(
    'mean')
test['TransactionAmt_to_mean_card6'] = test['TransactionAmt'] / test.groupby(['card6'])['TransactionAmt'].transform(
    'mean')

train['TransactionAmt_to_std_card1'] = train['TransactionAmt'] / train.groupby(['card1'])['TransactionAmt'].transform(
    'std')
train['TransactionAmt_to_std_card2'] = train['TransactionAmt'] / train.groupby(['card2'])['TransactionAmt'].transform(
    'std')
test['TransactionAmt_to_std_card1'] = test['TransactionAmt'] / test.groupby(['card1'])['TransactionAmt'].transform(
    'std')
test['TransactionAmt_to_std_card2'] = test['TransactionAmt'] / test.groupby(['card2'])['TransactionAmt'].transform(
    'std')

train['TransactionAmt_to_std_card3'] = train['TransactionAmt'] / train.groupby(['card3'])['TransactionAmt'].transform(
    'std')
train['TransactionAmt_to_std_card4'] = train['TransactionAmt'] / train.groupby(['card4'])['TransactionAmt'].transform(
    'std')
test['TransactionAmt_to_std_card3'] = test['TransactionAmt'] / test.groupby(['card3'])['TransactionAmt'].transform(
    'std')
test['TransactionAmt_to_std_card4'] = test['TransactionAmt'] / test.groupby(['card4'])['TransactionAmt'].transform(
    'std')

train['TransactionAmt_to_std_card5'] = train['TransactionAmt'] / train.groupby(['card5'])['TransactionAmt'].transform(
    'std')
train['TransactionAmt_to_std_card6'] = train['TransactionAmt'] / train.groupby(['card6'])['TransactionAmt'].transform(
    'std')
test['TransactionAmt_to_std_card5'] = test['TransactionAmt'] / test.groupby(['card5'])['TransactionAmt'].transform(
    'std')
test['TransactionAmt_to_std_card6'] = test['TransactionAmt'] / test.groupby(['card6'])['TransactionAmt'].transform(
    'std')

train['TransactionAmt_to_sum_card1'] = train['TransactionAmt'] / train.groupby(['card1'])['TransactionAmt'].transform(
    'sum')
train['TransactionAmt_to_sum_card2'] = train['TransactionAmt'] / train.groupby(['card2'])['TransactionAmt'].transform(
    'sum')
test['TransactionAmt_to_sum_card1'] = test['TransactionAmt'] / test.groupby(['card1'])['TransactionAmt'].transform(
    'sum')
test['TransactionAmt_to_sum_card2'] = test['TransactionAmt'] / test.groupby(['card2'])['TransactionAmt'].transform(
    'sum')

train['TransactionAmt_to_sum_card3'] = train['TransactionAmt'] / train.groupby(['card3'])['TransactionAmt'].transform(
    'sum')
train['TransactionAmt_to_sum_card4'] = train['TransactionAmt'] / train.groupby(['card4'])['TransactionAmt'].transform(
    'sum')
test['TransactionAmt_to_sum_card3'] = test['TransactionAmt'] / test.groupby(['card3'])['TransactionAmt'].transform(
    'sum')
test['TransactionAmt_to_sum_card4'] = test['TransactionAmt'] / test.groupby(['card4'])['TransactionAmt'].transform(
    'sum')

train['TransactionAmt_to_sum_card5'] = train['TransactionAmt'] / train.groupby(['card5'])['TransactionAmt'].transform(
    'sum')
train['TransactionAmt_to_sum_card6'] = train['TransactionAmt'] / train.groupby(['card6'])['TransactionAmt'].transform(
    'sum')
test['TransactionAmt_to_sum_card5'] = test['TransactionAmt'] / test.groupby(['card5'])['TransactionAmt'].transform(
    'sum')
test['TransactionAmt_to_sum_card6'] = test['TransactionAmt'] / test.groupby(['card6'])['TransactionAmt'].transform(
    'sum')

train['id_02_to_mean_card1'] = train['id_02'] / train.groupby(['card1'])['id_02'].transform('mean')
train['id_02_to_mean_card4'] = train['id_02'] / train.groupby(['card4'])['id_02'].transform('mean')
train['id_02_to_std_card1'] = train['id_02'] / train.groupby(['card1'])['id_02'].transform('std')
train['id_02_to_std_card4'] = train['id_02'] / train.groupby(['card4'])['id_02'].transform('std')

test['id_02_to_mean_card1'] = test['id_02'] / test.groupby(['card1'])['id_02'].transform('mean')
test['id_02_to_mean_card4'] = test['id_02'] / test.groupby(['card4'])['id_02'].transform('mean')
test['id_02_to_std_card1'] = test['id_02'] / test.groupby(['card1'])['id_02'].transform('std')
test['id_02_to_std_card4'] = test['id_02'] / test.groupby(['card4'])['id_02'].transform('std')

train['D15_to_mean_card1'] = train['D15'] / train.groupby(['card1'])['D15'].transform('mean')
train['D15_to_mean_card4'] = train['D15'] / train.groupby(['card4'])['D15'].transform('mean')
train['D15_to_std_card1'] = train['D15'] / train.groupby(['card1'])['D15'].transform('std')
train['D15_to_std_card4'] = train['D15'] / train.groupby(['card4'])['D15'].transform('std')

test['D15_to_mean_card1'] = test['D15'] / test.groupby(['card1'])['D15'].transform('mean')
test['D15_to_mean_card4'] = test['D15'] / test.groupby(['card4'])['D15'].transform('mean')
test['D15_to_std_card1'] = test['D15'] / test.groupby(['card1'])['D15'].transform('std')
test['D15_to_std_card4'] = test['D15'] / test.groupby(['card4'])['D15'].transform('std')

train['D15_to_mean_card4'] = train['D15'] / train.groupby(['card4'])['D15'].transform('mean')
train['D15_to_std_card4'] = train['D15'] / train.groupby(['card4'])['D15'].transform('std')

test['D15_to_mean_card4'] = test['D15'] / test.groupby(['card4'])['D15'].transform('mean')
test['D15_to_std_card4'] = test['D15'] / test.groupby(['card4'])['D15'].transform('std')

from sklearn.decomposition import PCA, FastICA
from sklearn.decomposition import TruncatedSVD
from sklearn.random_projection import GaussianRandomProjection
from sklearn.random_projection import SparseRandomProjection

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

used_features = ['card1', 'card2', 'card3', 'card5']

train[used_features] = train[used_features].fillna(-1.0)
test[used_features] = test[used_features].fillna(-1.0)

train, test = get_dc_feature(train, test, n_comp=3, used_features=used_features)

train['addr1_count_full'] = train['addr1'].map(
    pd.concat([train['addr1'], test['addr1']], ignore_index=True).value_counts(dropna=False))
test['addr1_count_full'] = test['addr1'].map(
    pd.concat([train['addr1'], test['addr1']], ignore_index=True).value_counts(dropna=False))

train['addr2_count_full'] = train['addr2'].map(
    pd.concat([train['addr2'], test['addr2']], ignore_index=True).value_counts(dropna=False))
test['addr2_count_full'] = test['addr2'].map(
    pd.concat([train['addr2'], test['addr2']], ignore_index=True).value_counts(dropna=False))

train['D15_to_mean_addr1'] = train['D15'] / train.groupby(['addr1'])['D15'].transform('mean')
train['D15_to_std_addr1'] = train['D15'] / train.groupby(['addr1'])['D15'].transform('std')

test['D15_to_mean_addr1'] = test['D15'] / test.groupby(['addr1'])['D15'].transform('mean')
test['D15_to_std_addr1'] = test['D15'] / test.groupby(['addr1'])['D15'].transform('std')

train["dist1_plus_dist2"] = train["dist1"] + train["dist2"]
train["dist1_minus_dist2"] = train["dist1"] - train["dist2"]
train["dist1_times_dist2"] = train["dist1"] * train["dist2"]
train["dist1_divides_dist2"] = train["dist1"] / train["dist2"]

test["dist1_plus_dist2"] = test["dist1"] + test["dist2"]
test["dist1_minus_dist2"] = test["dist1"] - test["dist2"]
test["dist1_times_dist2"] = test["dist1"] * test["dist2"]
test["dist1_divides_dist2"] = test["dist1"] / test["dist2"]

def transform_email(df):
    for col in ['P_emaildomain', 'R_emaildomain']:
        col1 = col.replace('domain', '_suffix')
        df[col1] = df[col].str.rsplit('.', expand=True).iloc[:, -1]

        col2 = col.replace('domain', 'Corp')
        df[col2] = df[col]
        df.loc[df[col].isin(['gmail.com', 'gmail']), col2] = 'Google'
        df.loc[df[col].isin(['yahoo.com', 'yahoo.com.mx', 'yahoo.co.uk', 'yahoo.co.jp',
                             'yahoo.de', 'yahoo.fr', 'yahoo.es', 'yahoo.com.mx',
                             'ymail.com']), col2] = 'Yahoo'
        df.loc[df[col].isin(['hotmail.com', 'outlook.com', 'msn.com', 'live.com.mx', 'hotmail.es',
                             'hotmail.co.uk', 'hotmail.de', 'outlook.es', 'live.com', 'live.fr',
                             'hotmail.fr']), col2] = 'Microsoft'
        df.loc[df[col].isin(['aol.com', 'verizon.net']), col2] = 'Verizon'
        df.loc[df[col].isin(['att.net', 'sbcglobal.net', 'bellsouth.net']), col2] = 'AT&T'
        df.loc[df[col].isin(['icloud.com', 'mac.com', 'me.com']), col2] = 'Apple'
        df.loc[df[col2].isin(df[col2].value_counts()[df[col2].value_counts() <= 1000].index), col2] = 'Others'

    return df

train = transform_email(train)
test = transform_email(test)

MFeatures = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9"]
for feature in MFeatures:
    train[feature + '_count_full'] = train[feature].map(
        pd.concat([train[feature], test[feature]], ignore_index=True).value_counts(dropna=False))
    test[feature + '_count_full'] = test[feature].map(
        pd.concat([train[feature], test[feature]], ignore_index=True).value_counts(dropna=False))

def transform_id_cols(df):
    #     df['id_01_cut'] = pd.cut(df['id_01'], bins=[-100, -30, -20, -10, -5, 0])

    df['id_05_d'] = df['id_05']
    df['id_05_d'].where(df[df['id_05_d'].notnull()]['id_05_d'] == 0, 1, inplace=True)

    #     df['id_06_cut'] = pd.cut(df['id_06'], bins=[-100, -10, -5, 0])
    df['id_06_d'] = df['id_06']
    df['id_06_d'].where(df[df['id_06_d'].notnull()]['id_06_d'] == 0, 1, inplace=True)

    # Dealing with id_30
    df['id_30_count'] = df['id_30'].map(df['id_30'].value_counts(dropna=False))
    df['System'] = df['id_30'].astype('str').str.split('.', expand=True)[0].str.split('_', expand=True)[0]
    df['SystemCorp'] = df['System'].str.split(expand=True)[0]

    # Dealing with id_31
    df['LastestBrowser'] = df['id_31']
    df.loc[
        df['LastestBrowser'].isin(['samsung browser 7.0', 'opera 53.0', 'mobile safari 10.0', 'chrome 63.0 for android',
                                   'google search application 49.0', 'firefox 60.0', 'edge 17.0', 'chrome 69.0',
                                   'chrome 67.0 for android', 'chrome 64.0', 'chrome 63.0 for ios', 'chrome 65.0',
                                   'chrome 64.0 for android', 'chrome 64.0 for ios', 'chrome 66.0',
                                   'chrome 65.0 for android', 'chrome 65.0 for ios', 'chrome 66.0 for android',
                                   'chrome 66.0 for ios']), 'LastestBrowser'] = 1
    df.loc[df['LastestBrowser'].str.len() > 1, 'LastestBrowser'] = 0

    df['id_31_count'] = df['id_31'].map(df['id_31'].value_counts(dropna=False))

    df['MSBrowser'] = df['id_31'].str.contains('edge|ie|microsoft', case=False) * 1
    df['AppleBrowser'] = df['id_31'].str.contains('safari', case=False) * 1
    df['GoogleBrowser'] = df['id_31'].str.contains('chrome', case=False) * 1
    df['BrowserType'] = df['id_31']
    df.loc[df['BrowserType'].str.contains('samsung', case=False, na=False), 'BrowserType'] = 'Samsung'
    df.loc[df['BrowserType'].str.contains('safari', case=False, na=False), 'BrowserType'] = 'Apple'
    df.loc[df['BrowserType'].str.contains('chrome|google', case=False, na=False), 'BrowserType'] = 'Google'
    df.loc[df['BrowserType'].str.contains('firefox', case=False, na=False), 'BrowserType'] = 'Mozilla'
    df.loc[df['BrowserType'].str.contains('edge|ie|microsoft', case=False, na=False,
                                          regex=True), 'BrowserType'] = 'Microsoft'
    df.loc[df['BrowserType'].isin(df['BrowserType'].value_counts()[df['BrowserType'].value_counts() < 1000].index), [
        'BrowserType']] = 'other'

    # Dealing with id_33
    df['id_33_count'] = df['id_33'].map(df['id_33'].value_counts(dropna=False))
    df['DisplaySize'] = df['id_33'].str.split('x', expand=True)[0].astype('float') * \
                        df['id_33'].str.split('x', expand=True)[1].astype('float')
    df['DisplaySize'].replace(0, np.nan, inplace=True)
    df['DisplaySize'] = (df['DisplaySize'] / df['DisplaySize'].min()).round(0)

    # Try easy combining
    for feature in ['id_02__id_20', 'id_13__id_17', 'id_02__D8', 'D11__DeviceInfo',
                    'DeviceInfo__P_emaildomain', 'card2__dist1', 'card1__card5',
                    'card2__id_20', 'card5__P_emaildomain', 'addr1__card1']:
        f1, f2 = feature.split('__')
        df[feature] = df[f1].astype(str) + '_' + df[f2].astype(str)
    for col in ['id_30', 'id_31', 'id_33', 'DeviceInfo']:
        df[col + '_DeviceTpye'] = train[col] + '_' + train['DeviceType']

    return df

train = transform_id_cols(train)
test = transform_id_cols(test)

def transform_DeviceInfo(df):
    df['DeviceCorp'] = df['DeviceInfo']
    df.loc[df['DeviceInfo'].str.contains('HUAWEI|HONOR', case=False, na=False, regex=True), 'DeviceCorp'] = 'HUAWEI'
    df.loc[df['DeviceInfo'].str.contains('OS', na=False, regex=False), 'DeviceCorp'] = 'APPLE'
    df.loc[df['DeviceInfo'].str.contains('Idea|TA', case=False, na=False), 'DeviceCorp'] = 'Lenovo'
    df.loc[df['DeviceInfo'].str.contains('Moto|XT|Edison', case=False, na=False), 'DeviceCorp'] = 'Moto'
    df.loc[df['DeviceInfo'].str.contains('MI|Mi|Redmi', na=False), 'DeviceCorp'] = 'Mi'
    df.loc[df['DeviceInfo'].str.contains('VS|LG|EGO', na=False), 'DeviceCorp'] = 'LG'
    df.loc[
        df['DeviceInfo'].str.contains('ONE TOUCH|ALCATEL', case=False, na=False, regex=False), 'DeviceCorp'] = 'ALCATEL'
    df.loc[df['DeviceInfo'].str.contains('ONE A', na=False, regex=False), 'DeviceCorp'] = 'ONEPLUS'
    df.loc[df['DeviceInfo'].str.contains('OPR6', na=False, regex=False), 'DeviceCorp'] = 'HTC'
    df.loc[df['DeviceInfo'].str.contains('Nexus|Pixel', case=False, na=False, regex=True), 'DeviceCorp'] = 'google'
    df.loc[df['DeviceInfo'].str.contains('STV', na=False, regex=False), 'DeviceCorp'] = 'blackberry'
    df.loc[df['DeviceInfo'].str.contains('ASUS', case=False, na=False, regex=False), 'DeviceCorp'] = 'ASUS'
    df.loc[df['DeviceInfo'].str.contains('BLADE', case=False, na=False, regex=False), 'DeviceCorp'] = 'ZTE'

    df['DeviceCorp'] = \
    df['DeviceInfo'].astype('str').str.split(':', expand=True)[0].str.split('-', expand=True)[0].str.split(expand=True)[
        0]

    df.loc[df['DeviceInfo'].isin(['rv', 'SM', 'GT', 'SGH']), 'DeviceCorp'] = 'SAMSUNG'
    df.loc[df['DeviceInfo'].str.startswith('Z', na=False), 'DeviceCorp'] = 'ZTE'
    df.loc[df['DeviceInfo'].str.startswith('KF', na=False), 'DeviceCorp'] = 'Amazon'

    for i in ['D', 'E', 'F', 'G']:
        df.loc[df['DeviceInfo'].str.startswith(i, na=False), 'DeviceCorp'] = 'SONY'

    minority = df['DeviceCorp'].value_counts()[df['DeviceCorp'].value_counts() < 100].index
    df.loc[df['DeviceCorp'].isin(minority), 'DeviceCorp'] = 'Other'
    df['DeviceCorp'] = df['DeviceCorp'].str.upper()

    return df

train = transform_DeviceInfo(train)
test = transform_DeviceInfo(test)

target = "isFraud"
# Label Encoding
for f in tqdm_notebook([feature for feature in train.columns if feature != target]):
    if train[f].dtype == 'object' or test[f].dtype == 'object':
        lbl = LabelEncoder()
        temp = pd.DataFrame(train[f].astype(str).append(test[f].astype(str)))
        lbl.fit(temp[f])
        train[f] = lbl.transform(list(train[f].astype(str)))
        test[f] = lbl.transform(list(test[f].astype(str)))

def transform_number(df):
    df['id_02_log'] = np.log10(df['id_02'])

    df['C5_d'] = df['C5']
    df['C5_d'].where(df['C5'] == 0, 1, inplace=True)

    df['D8_mul_D9'] = df['D8'] * df['D9']

    df['TransAmt_mul_dist1'] = df['TransactionAmt'] * df['dist1']
    df['TransAmt_per_TransDT'] = df['TransactionAmt'] * 24 * 60 * 60 / df['TransactionDT']

    return df

train = transform_number(train)
test = transform_number(test)

for feature in tqdm_notebook(['id_02__id_20', 'id_02__D8', 'D11__DeviceInfo', 'DeviceInfo__P_emaildomain',
                              'P_emaildomain__C2',
                              'P_emaildomain__card1', 'P_emaildomain__card2',
                              'card2__dist1', 'card1__card5', 'card2__id_20', 'card5__P_emaildomain',
                              'addr1__card1', 'card2__card4', 'card4__card6'
                              ]):
    f1, f2 = feature.split('__')
    train[feature] = train[f1].astype(str) + '_' + train[f2].astype(str)
    test[feature] = test[f1].astype(str) + '_' + test[f2].astype(str)

    le = LabelEncoder()
    le.fit(list(train[feature].astype(str).values) + list(test[feature].astype(str).values))
    train[feature] = le.transform(list(train[feature].astype(str).values))
    test[feature] = le.transform(list(test[feature].astype(str).values))

for feature in tqdm_notebook([
    'P_emaildomain__card1__card2', 'addr1__card1__card2'
]):
    f1, f2, f3 = feature.split('__')
    train[feature] = train[f1].astype(str) + '_' + train[f2].astype(str) + '_' + train[f3].astype(str)
    test[feature] = test[f1].astype(str) + '_' + test[f2].astype(str) + '_' + test[f3].astype(str)

    le = LabelEncoder()
    le.fit(list(train[feature].astype(str).values) + list(test[feature].astype(str).values))
    train[feature] = le.transform(list(train[feature].astype(str).values))
    test[feature] = le.transform(list(test[feature].astype(str).values))

X = train.sort_values('TransactionDT').drop(['isFraud', 'TransactionDT', 'TransactionID'], axis=1)
y = train.sort_values('TransactionDT')['isFraud']
test_X = test.sort_values('TransactionDT').drop(['TransactionDT', 'TransactionID'], axis=1)

def LGB_bayesian(
    #learning_rate,
    num_leaves, bagging_fraction, feature_fraction, min_child_weight, min_data_in_leaf, max_depth,
    reg_alpha, reg_lambda):

    num_leaves = int(num_leaves)
    min_data_in_leaf = int(min_data_in_leaf)
    max_depth = int(max_depth)
    assert type(num_leaves) == int
    assert type(min_data_in_leaf) == int
    assert type(max_depth) == int

    params = {
        'num_leaves': num_leaves,
        'min_data_in_leaf': min_data_in_leaf,
        'min_child_weight': min_child_weight,
        'bagging_fraction': bagging_fraction,
        'feature_fraction': feature_fraction,
        # 'learning_rate' : learning_rate,
        'max_depth': max_depth,
        'reg_alpha': reg_alpha,
        'reg_lambda': reg_lambda,
        'objective': 'binary',
        'save_binary': True,
        'seed': 1337,
        'feature_fraction_seed': 1337,
        'bagging_seed': 1337,
        'drop_seed': 1337,
        'data_random_seed': 1337,
        'boosting_type': 'gbdt',
        'verbose': 1,
        'is_unbalance': False,
        'boost_from_average': True,
        'metric': 'auc'}

    lgb_sub = sub.copy()
    lgb_sub['isFraud'] = 0


    for fold_n, (train_index, valid_index) in enumerate(folds.split(X)):

        if fold_n == 4:
            break
        start_time = time()
        print('Training on fold {}'.format(fold_n + 1))

        trn_data = lgb.Dataset(X.iloc[train_index], label=y.iloc[train_index])
        val_data = lgb.Dataset(X.iloc[valid_index], label=y.iloc[valid_index])
        clf = lgb.train(params, trn_data, num_boost_round=10000, valid_sets=[val_data], verbose_eval=-1,
                        early_stopping_rounds=500)

        pred = clf.predict(test_X)

        lgb_sub['isFraud'] = lgb_sub['isFraud'] + pred / (n_fold - 1)
        print('Fold {} finished in {}'.format(fold_n + 1, str(datetime.timedelta(seconds=time() - start_time))))

    test = pd.read_csv('../temp/test_label.csv', usecols=["TransactionID", "isFraud"], nrows=NROWS)
    df1 = test.merge(lgb_sub, on="TransactionID", how="left")
    score = roc_auc_score(df1["isFraud_x"], df1["isFraud_y"])

    return score

bounds_LGB = {
    'num_leaves': (27, 500),
    'min_data_in_leaf': (20, 200),
    'bagging_fraction' : (0.1, 0.9),
    'feature_fraction' : (0.1, 0.9),
    #'learning_rate': (0.01, 0.3),
    'min_child_weight': (0.00001, 0.01),
    'reg_alpha': (1, 2),
    'reg_lambda': (1, 2),
    'max_depth':(-1,50),
}

LGB_BO = BayesianOptimization(LGB_bayesian, bounds_LGB, random_state=42)
print(LGB_BO.space.keys)
init_points = 10
n_iter = 15

with warnings.catch_warnings():
    warnings.filterwarnings('ignore')
    LGB_BO.maximize(init_points=init_points, n_iter=n_iter, acq='ucb', xi=0.0, alpha=1e-6)

print('Total training time is {}'.format(str(datetime.timedelta(seconds=time() - training_start_time))))
print(LGB_BO.max['target'])
print(LGB_BO.max['params'])
