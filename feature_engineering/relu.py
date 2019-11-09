import pandas as pd
pd.set_option("display.max_columns", 500)
import plotly.offline as py
py.init_notebook_mode(connected=True)
from tqdm import tqdm_notebook
import gc
import warnings
warnings.filterwarnings('ignore')

NROWS = None

train_identity = pd.read_csv('../input/train_identity.csv', nrows=NROWS)
train_transaction = pd.read_csv('../input/train_transaction.csv', nrows=NROWS)
train = train_transaction.merge(train_identity, how='left', on='TransactionID')

test_identity = pd.read_csv('../input/test_identity.csv', nrows=NROWS)
test_transaction = pd.read_csv('../input/test_transaction.csv', nrows=NROWS)
test = test_transaction.merge(test_identity, how='left', on='TransactionID')

gc.enable()
del train_identity, train_transaction
del test_identity, test_transaction
gc.collect()

target = "isFraud"
test[target] = -1
df = train.append(test)
df.index = range(len(df))

df['uid'] = df["card1"].apply(lambda x: str(x)) + "_" + df["card2"].apply(lambda x: str(x)) +\
                "_" + df["card3"].apply(lambda x: str(x)) + "_" + df["card4"].apply(lambda x: str(x)) +\
                "_" + df["card5"].apply(lambda x: str(x)) + "_" + df["card6"].apply(lambda x: str(x)) +\
                "_" + df["addr1"].apply(lambda x: str(x)) + "_" + df["addr2"].apply(lambda x: str(x)) +\
                "_" + df["P_emaildomain"].apply(lambda x: str(x)) 

df["day"] = (df["TransactionDT"] + 3600 * 12) // (24 * 60 * 60)
feature_list = ["uid", target, "D1", "D10", "day", "TransactionDT", "TransactionID"]
train = df.loc[df[target] != -1, feature_list]
temp = train.groupby('uid').agg({target: ['mean', 'count', 'sum']})
uid_list = list(temp.loc[(temp[target]['mean'] ==1) & (temp[target]['sum'] > 0)].index)
sub1 = pd.read_csv('../output/ens9.csv')
sub1 = sub1.merge(df[feature_list], on = "TransactionID", how = "left")
sub1["last_day"] = sub1["day"] - sub1["D1"]
subx = sub1.loc[(sub1["uid"].isin(uid_list)) & (sub1["last_day"] <= 183) & (sub1["last_day"] >= 1)]
train.loc[(train["uid"] == list(subx["uid"])[i])]

fraud_Uids = []
for uid in tqdm_notebook(train["uid"].unique()[-3000:]):
    
    temp1 = df.loc[(df["uid"] == uid) & (df[target] == 1), feature_list]
    
    temp2 = df.loc[(df["uid"] == uid) & (df[target] == 0), feature_list]
    
    temp3 = df.loc[(df["uid"] == uid) & (df[target] == -1), feature_list]
    
    if (temp1.TransactionID.min() > temp2.TransactionID.max() and temp3.shape[0] > 0):
        
        print(uid, temp3.shape[0])
        fraud_Uids.append([uid, temp3.shape[0]])

fraud_Uids = pd.DataFrame(fraud_Uids)
fraud_Uids.columns = ['uid', 'train_cnt', 'test_cnt']

fraud_Uids.to_csv("./fraud_Uids.csv", index=False)

sub1 = sub.merge(df[["TransactionID", "uid"]], on = "TransactionID", how = "left")
sub1.loc[sub1["uid"].isin(uid_list), "isFraud"] = 1
sub1[["TransactionID", "isFraud"]].to_csv("../output/ens9_rule3.csv", index=False)