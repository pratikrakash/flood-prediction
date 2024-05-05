import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler
from sklearn.model_selection import train_test_split
import tensorflow as tf
import keras_tuner as kt
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, accuracy_score, classification_report, confusion_matrix


class FloodPrediction:
    '''This class creates an LSTM model that predicts flood events based on \
    monthly rainfall data'''

    def __init__(self, path="../data/", data_file="chennai-monthly-rains.csv", target_file="chennai-monthly-manual-flood.csv"):
        '''Object initializer.'''


        self._model = tf.keras.Sequential()
        self._history = tf.keras.callbacks.History()

        self._df = pd.DataFrame()
        self._X = pd.DataFrame()
        self._y = pd.DataFrame()
        self._X_train = pd.DataFrame()
        self._X_test = pd.DataFrame()
        self._X_val = pd.DataFrame()
        self._y_train = pd.DataFrame()
        self._y_test = pd.DataFrame()
        self._y_val = pd.DataFrame()
        self.path = path
        self.lag = int
        self.fore = int
        self.sequence = int

        # read files and format data
        self.load_data(data_file, target_file)

        # data-target split
        self.make_data_target()

        # z-score
        self.apply_standard_scaler()

        # normalise data
        self.apply_minmax_scaler()

        # over- (SMOTE) and under-sampling
        self.apply_over_under_sampling()

        # lag and forecast
        self.convert_to_supervised()

        # reshape data
        self.convert_shape_to_3d()

        # data splitting
        self.train_test_split()

        # train-validation split
        self.train_validation_split()

    def load_data(self,
                  data,
                  target,
                  data_index='Year',
                  target_index='year',
                  collapse_data_columns=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                  collapse_target_columns=["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
                  data_column_name='months_rain',
                  target_column_name='months_flood',
                  drop_data_columns=["Year", "Total"],
                  drop_target_columns=["year"]):
        '''This method loads training data and supervised learning targets.'''
    
        # read data
        df_rain = pd.read_csv(self.path + data)
        df_flood = pd.read_csv(self.path + target)

        # clean data
        if df_rain[data_index].max() < df_flood[target_index].max():
            df_flood = df_flood[(df_flood[target_index] <= df_rain[data_index].max())]

        if df_rain[data_index].max() > df_flood[target_index].max():
            df_rain = df_rain[(df_rain[data_index] <= df_flood[target_index].max())]

        # merge datasets
        #   TODO: remove second 'year' column added by merging
        self._df = pd.merge(df_rain, df_flood, left_on=data_index, right_on=target_index)

        # concat columns
        self._df = pd.concat([self._df, self._df[collapse_data_columns].T.stack().reset_index(name=data_column_name)[data_column_name]], axis=1)
        self._df = pd.concat([self._df, self._df[collapse_target_columns].T.stack().reset_index(name=target_column_name)[target_column_name]], axis=1)

        # drop unnecessary columns
        self._df.drop(inplace=True, columns=drop_data_columns + collapse_data_columns)
        self._df.drop(inplace=True, columns=drop_target_columns + collapse_target_columns)

    def make_data_target(self):
        '''This method splits the dataframe into data (X) and supervised learning targets (y).'''
        self._X = self._df[self._df.columns[:-1]]
        self._y = self._df[self._df.columns[-1:]]

    def apply_standard_scaler(self):
        '''This method applies the standard scaler to the data.'''

        std_scaler = StandardScaler()
        X_zerod = std_scaler.fit_transform(self._X)
        self._X = pd.DataFrame(X_zerod, columns=list(self._X.columns))

    def apply_minmax_scaler(self):
        '''This method applies the minmax scaler to the data.'''

        minmax_scaler = MinMaxScaler()
        X_scaled = minmax_scaler.fit_transform(self._X)
        self._X = pd.DataFrame(X_scaled, columns=list(self._X.columns))

    def apply_over_under_sampling(self, smote_sampling_strategy=0.1, smote_k_neighbors=2):
        '''This method applies oversampling (SMOTE) and undersampling (RandomUnderSampler) to both data and targets.'''

        oversample = SMOTE(sampling_strategy=smote_sampling_strategy, k_neighbors=smote_k_neighbors)
        understample = RandomUnderSampler()

        self._X, self._y = oversample.fit_resample(self._X, self._y)
        self._X, self._y = understample.fit_resample(self._X, self._y)

    def convert_to_supervised(self, lag=1,
                              forecast=1,
                              lag_column_pattern='var%d(t-%d)',
                              original_column_pattern='var%d(t)',
                              forecast_column_pattern='var%d(t+%d)'):
        '''This method converts the training data to a format for supervised learning.'''

        # Adapted from: J. Brownlee, “How to Convert a Time Series to a Supervised Learning Problem in Python,” Machine Learning Mastery, May 07, 2017. https://machinelearningmastery.com/convert-time-series-supervised-learning-problem-python/
        cols, names = list(), list()
        for i in range(lag, 0, -1):
            cols.append(self._X.shift(i))
            names += [(lag_column_pattern % (j+1, i)) for j in range(self._X.shape[1])]
        for i in range(0, forecast):
            cols.append(self._X.shift(-1))
        if i == 0:
            names += [(original_column_pattern % (j+1)) for j in range(self._X.shape[1])]
        else:
            names += [(forecast_column_pattern % (j+1, i)) for j in range(X.shape[1])]
        self._X = pd.concat(cols, axis=1)
        self._X.columns = names
        self._X.dropna(inplace=True)

    def convert_shape_to_3d(self, sequence=20):
        '''This method converts input data shape from (n,n) to (n,n,n).'''

        # Adapted from: S. S. Bhakta, “Multivariate Time Series Forecasting with LSTMs in Keras,” GeeksforGeeks, Feb. 17, 2024. https://www.geeksforgeeks.org/multivariate-time-series-forecasting-with-lstms-in-keras/ (accessed May 02, 2024).
        dfX = []
        dfY = []
        for i in range(0, len(self._X) - sequence):
            data = [[self._X[col].iloc[i+j] for col in self._X.columns] for j in range(0, sequence)]
            dfX.append(data)
            dfY.append(self._y[['months_flood']].iloc[i + sequence].values)
        self._X, self._y = np.array(dfX), np.array(dfY)

    def train_test_split(self, test_size=0.2, random_state=42):
        '''This method performs holdout data splitting to create test data.'''

        self._X_train, self._X_test, self._y_train, self._y_test = train_test_split(self._X, self._y, test_size=test_size, random_state=random_state)

    def train_validation_split(self, test_size=0.1, random_state=42):
        '''This method performs holdout data splitting to create validation data.'''

        self._X_train, self._X_val, self._y_train, self._y_val = train_test_split(self._X_train, self._y_train, test_size=test_size, random_state=random_state)

    def build_model(self,
                    hp, hp_tune_min_units=32,
                    hp_tune_max_units=512,
                    hp_tune_units_step=32,
                    hp_tune_lrs=[1e-2, 1e-3, 1e-4],
                    metrics=[
                        tf.keras.metrics.BinaryAccuracy(name='accuracy'),
                        tf.keras.metrics.BinaryCrossentropy(name='log loss'),
                        tf.keras.metrics.TruePositives(name='TP'),
                        tf.keras.metrics.TrueNegatives(name='TN'),
                        tf.keras.metrics.FalsePositives(name='FP'),
                        tf.keras.metrics.FalseNegatives(name='FN'),
                        tf.keras.metrics.Precision(name='precision'),
                        tf.keras.metrics.Recall(name='recall'),
                        tf.keras.metrics.AUC(name='prc', curve='PR')],
                    dropout=0.2,
                    activation='sigmoid',
                    loss='BinaryCrossentropy'):
        '''This method builds and compiles a new LSTM model.'''

        # hyper parameter tuning
        hp_units = hp.Int('units', min_value=hp_tune_min_units, max_value=hp_tune_max_units, step=hp_tune_units_step)
        hp_units_2 = hp.Int('units2', min_value=hp_tune_min_units, max_value=hp_tune_max_units, step=hp_tune_units_step)
        hp_learning_rate = hp.Choice('learning_rate', values=hp_tune_lrs)

        # force GPU
        #with tf.device('/GPU:0'):

        # LSTM
        model = tf.keras.Sequential()
        model.add(tf.keras.Input((self._X_train.shape[1], self._X_train.shape[2])))
        model.add(tf.keras.layers.LSTM(units=hp_units, return_sequences=True))
        model.add(tf.keras.layers.LSTM(units=hp_units_2))
        
        # drop data to control overfitting
        model.add(tf.keras.layers.Dropout(dropout))
        
        model.add(tf.keras.layers.Dense(units=1, activation=activation, bias_initializer=tf.keras.initializers.Constant(np.log([pos/neg]))))
        model.compile(loss=loss, optimizer=tf.keras.optimizers.Adam(learning_rate=hp_learning_rate), metrics=metrics)
        model.summary()

        #print(X_train.shape[1])
        
        self._model = model

        return model
        
    def tune_model(self,
                   objective=kt.Objective('prc', direction='max'),
                   tuner_max_epochs=10,
                   factor=3,
                   search_epochs=50,
                   callbacks=[tf.keras.callbacks.EarlyStopping(monitor='val_prc', verbose=1, patience=3, mode='max', restore_best_weights=True)],
                   num_trials=1):
        '''This method tunes the hyperparameters of the model.'''

        tuner = kt.Hyperband(self.build_model, objective=objective, max_epochs=tuner_max_epochs, factor=factor)
        tuner.search(self._X_train, self._y_train, epochs=search_epochs, callbacks=callbacks)
        best_hp = tuner.get_best_hyperparameters(num_trials=num_trials)[0]
        
        print(best_hp.get('units'), best_hp.get('learning_rate'))
        
        self._model = tuner.hypermodel.build(best_hp)

    def fit_model(self,
                  epochs=20,
                  batch_size=1,
                  validation_data=None,
                  verbose=1,
                  callbacks=[tf.keras.callbacks.EarlyStopping(monitor='val_prc', verbose=1, patience=3, mode='max', restore_best_weights=True)]):
        '''This method trains the model.'''

        if validation_data == None:
            validation_data = (self._X_val, self._y_val)

        self._history = self._model.fit(self._X_train, self._y_train, epochs=epochs, batch_size=batch_size, validation_data=validation_data, verbose=verbose, callbacks=callbacks)


    def predict(self, data=None, threshold=0.9):
        '''This method makes a prediction using the model.'''

        if data == None:
            data = self._X_test

        y_pred = self._model.predict(data)
        y_pred = np.where(y_pred > threshold, 1, 0) # magic number = 0.026; with weights = ~0.5325
        y_pred = pd.DataFrame(y_pred, columns=list(self._df[self._df.columns[-1:]]))
        
        return y_pred
 
    def evaluate(self):
        '''This  method makes an evaluation report on a prediction.'''

        self._model.evaluate(self._X_test, self._y_test)

    def get_dataframe(self):
        '''Accessor returns the raw pandas dataframe used for training the model.'''
        return self._df

    def get_history(self):
        '''Accessor returns the tf.keras.callbacks.History object.'''
        return self._history

    def get_data(self):
        '''Accessor returns the data used to train the model.'''
        return self._X

    def get_target(self):
        '''Accessor returns the supervised learning targets/labels used to train the model.'''
        return self._y

    def get_data_train_split(self):
        '''Accessor returns the data training split after data splitting used for training the model.'''
        return self._X_train

    def get_target_train_split(self):
        '''Accessor returns the target training split after data splitting used for training the model.'''
        return self._y_train

    def get_data_test_split(self):
        '''Accessor returns the data test split after data splitting used for training the model.'''
        return self._X_test

    def get_target_test_split(self):
        '''Accessor returns the target test split after data splitting used for training the model.'''
        return self._y_test

    def get_data_validation_split(self):
        '''Accessor returns the data validation split after data splitting used for validating the trained model.'''
        return self._X_val

    def get_target_validation_split(self):
        '''Accessor returns the target validation split after data splitting used for validating the trained model.'''
        return self._y_val


if __name__ == "__main__":

    # create a model for testing
    new_model = FloodPrediction()

    # stats
    print(new_model.get_dataframe()[['months_rain', 'months_flood']].describe())

    # check shape
    print("Original shape:", new_model.get_dataframe().shape)

    # visualise data
    #df_rain.plot(x="Year")
    #df_flood.plot(x="year")
    #plt.show()

    # check data balance
    # Adapted from: “Classification on imbalanced data | TensorFlow Core,” TensorFlow. https://www.tensorflow.org/tutorials/structured_data/imbalanced_data
    neg, pos = np.bincount(new_model.get_dataframe()['months_flood'])
    t = neg + pos
    print(f"Total: %d; positive: %d (%.2f%% of total)" % (t, pos, (100*pos/t)))

    # TODO: convert data to log-space?

    # check shape after sampling target data
    print("X:", new_model.get_data().shape)
    print("y:", new_model.get_target().shape)

    #plt.plot(X)
    #plt.title("MinMax")
    #plt.show()

    # over- (SMOTE) and under-sampling
    print("Y", new_model.get_target())

    # check shape after reshaping
    print("X:", new_model.get_data().shape)
    print("y:", new_model.get_target().shape)

    # check shape after splitting
    print("X_train:", new_model.get_data_train_split().shape, "X_test:", new_model.get_data_test_split().shape)
    print("y_train:", new_model.get_target_train_split().shape, "y_test:", new_model.get_target_test_split().shape)
    print("X_val:", new_model.get_data_validation_split().shape, "y_val:", new_model.get_target_validation_split().shape)

    # hyperparameter search
    new_model.tune_model()

    # create class weights
    # Adapted from: “Classification on imbalanced data: Tensorflow Core,” TensorFlow, https://www.tensorflow.org/tutorials/structured_data/imbalanced_data (accessed May 2, 2024).
    #weight_neg = (1 / neg) * (t / 2.0)
    #weight_pos = (1 / pos) * (t / 2.0)

    #weights = {0: weight_neg, 1: weight_pos}; print("Weights:", weights)

    # training
    new_model.fit_model()

    plt.plot(new_model.get_history().history['loss'])
    plt.plot(new_model.get_history().history['accuracy'])
    plt.ylabel("loss / accuracy")
    plt.xlabel("Epoch")
    plt.legend(['loss', 'accuracy'])
    plt.title("Training")
    plt.show()

    # make prediction
    y_pred = new_model.predict()

    # evaluate prediction
    new_model.evaluate()

    print("Actual:")
    print(pd.DataFrame(new_model.get_target_test_split(), columns=list(new_model.get_dataframe()[new_model.get_dataframe().columns[-1:]])))
    print("Predictions:")
    print(y_pred)
    print("MSE:", mean_squared_error(new_model.get_target_test_split(), y_pred))
    print("MAE:", mean_absolute_error(new_model.get_target_test_split(), y_pred))
    print("R2:", r2_score(new_model.get_target_test_split(), y_pred))
    print("Accuracy:", accuracy_score(new_model.get_target_test_split(), y_pred))
    print(classification_report(new_model.get_target_test_split(), y_pred))
    print(confusion_matrix(new_model.get_target_test_split(), y_pred))
