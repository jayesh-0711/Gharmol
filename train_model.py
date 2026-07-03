import pandas as pd
import numpy as np
import pickle
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression

# 1. Load dataset
df = pd.read_csv("data/Bengaluru_House_Data.csv")

print("Dataset Loaded")

# 2. Drop unnecessary columns
df = df.drop(['area_type', 'availability', 'society'], axis=1)

# 3. Convert total_sqft column
def convert_sqft(x):
    try:
        if '-' in str(x):
            a, b = x.split('-')
            return (float(a) + float(b)) / 2
        return float(x)
    except:
        return None

df['total_sqft'] = df['total_sqft'].apply(convert_sqft)

# 4. Remove missing values
df = df.dropna()

# 5. Extract BHK from size column
df['BHK'] = df['size'].apply(lambda x: int(x.split(' ')[0]))
df = df.drop('size', axis=1)

# 6. Convert location to numeric values
df['location'] = df['location'].astype('category').cat.codes

# 7. Define features and target
X = df[['location', 'total_sqft', 'BHK', 'bath']]
y = df['price']

# 8. Train test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# 9. Train model
model = LinearRegression()
model.fit(X_train, y_train)

print("Model trained successfully")

# 10. Save model
pickle.dump(model, open("model.pkl", "wb"))
 
print("model.pkl file created successfully")