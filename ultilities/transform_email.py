import numpy as np
import pandas as pd

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