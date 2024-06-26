import sys
import numpy as np
import pandas as pd
import random
import math

class DataGenerator:
    EFFECT_SCALE_RANGE = 5
    EFFECT_EXPONENT_RANGE = 5

    all_functions = [
        (lambda x, sign, c, n, i: sign * c * x * (1 / (DataGenerator.EFFECT_SCALE_RANGE))),
        (lambda x, sign, c, n, i: sign * ((c * x) ** n) * (1 / (DataGenerator.EFFECT_SCALE_RANGE ** DataGenerator.EFFECT_EXPONENT_RANGE))),
        (lambda x, sign, c, n, i: sign * ((c * x) ** (1/(n + 1)))),
        (lambda x, sign, c, n, i: sign * math.log(abs(c) * x + 1, n + 1)),
        (lambda x, sign, c, n, i: sign * (x and i)),
        (lambda x, sign, c, n, i: sign * (x or i)),
        (lambda x, sign, c, n, i: sign * (x ^ i))
        ]

    def __init__(self, 
                 num_cols=10, 
                 num_rows=10, 
                 num_important=1, 
                 num_interaction_terms=0, 
                 interactions=None, 
                 monotonic=False,
                 importance_ranking="scaled", 
                 effects=None, 
                 effect_types="all",
                 frequencies=None, 
                 correlation_scale=0.9, 
                 correlation_distribution='normal', 
                 target='target', 
                 intercept=0, 
                 noise_distribution='normal', 
                 noise_scale=0, 
                 rng_seed=None):
        """
        Initialize the DataGenerator with specified parameters.

        Parameters:
        - num_cols (int, optional): Number of columns/features in the dataset (default is 10).
        - num_rows (int, optional): Number of rows in the dataset (default is 10).
        - num_important (int, optional): Number of important columns (default is 1).
        - num_interaction_terms (int, optional): Number of interaction terms (default is the value of num_important).
        - interactions (dict-like, optional): Interaction terms and their correlations,
            with format interactions[i] = (j, c) implying that in any given row,
            variable i will be set to the value of variable j approximately c% of the time.
            (negative c means variable i will be set to the opposite of variable j c% of the time)
            (default is None)
        - monotonic (bool, optional): Whether effects are monotonic (default is False).
        - importance_ranking (str, optional): Method of importance ranking ('constant' or 'scaled') (default is 'scaled').
        - effects (dict-like of function, optional): Effects applied to target, with format
            effects[i] = f implying f(variable i) will be added to the target for every row
            (default is None)
        - effect_types (str or list-like of function, optional): Effects to choose from
            Types must be either one of ('all', 'linear', 'constant') or a list of functions
            (default is 'all')
        - frequencies (dict-like, optional): Frequencies of 1s in binary columns (default is an empty dictionary).
        - correlation_scale (float): Scale of correlation for interactions (default is 0.9).
        - correlation_distribution (str, optional): Distribution type for correlations ('normal', 'uniform', 'beta') (default is 'normal').
        - target (str, optional): Name of the target column (default is 'target').
        - intercept (float, optional): Intercept for the target variable (default is 0).
        - noise_distribution (str, optional): Distribution type for noise ('normal', 'uniform', 'gamma') (default is 'normal').
        - noise_scale (float, optional): Scale of the noise (default is 0).
        - rng_seed (float, optional): Seed for RNG (default is random seed).
        """
        
        # Record initialization params
        self.num_cols = num_cols
        self.num_rows = num_rows
        self.num_important = num_important
        self.num_interaction_terms = num_interaction_terms
        self.interactions = interactions if interactions is not None else {}
        self.monotonic = monotonic
        self.importance_ranking = importance_ranking
        self.effects = effects if effects is not None else {}
        self.effect_types = effect_types
        self.frequencies = frequencies if frequencies is not None else {}
        self.correlation_scale = correlation_scale
        self.correlation_distribution = correlation_distribution
        self.target = target
        self.intercept = intercept
        self.noise_distribution = noise_distribution
        self.noise_scale = noise_scale

        # Generate default parameters
        self.rng_seed = random.randint(0, sys.maxsize) if rng_seed is None else rng_seed
        self.rng = np.random.default_rng(self.rng_seed)
        self.cols = range(num_cols)

        # set frequencies randomly if not specified
        for col in self.cols:
            if col not in self.frequencies.keys():
                self.frequencies[col] = self.rng.random()

        # Handle effects
        self.functions = DataGenerator.all_functions

        if effect_types == 'all':
            self.functions = DataGenerator.all_functions
        elif effect_types == 'linear':
            self.functions = DataGenerator.all_functions[0:1]
        elif effect_types == 'constant':
            self.functions = [lambda x, **kwargs: x]

        self.important_variables = self.cols[:num_important]
        generated_effects = self.random_interaction(self.important_variables, functions=self.functions)

        # Include user-supplied effects
        for variable, effect in self.effects.items():
            generated_effects[variable] = effect
        self.effects = generated_effects

        # Re-calculate important variables based on impact
        self.important_variables = [variable for variable, function in enumerate(self.effects) if (function(0) !=0 or function(1) != 0)]

        # Handle interaction terms
        self.interaction_terms = self.cols[-self.num_interaction_terms:]
        generated_interactions = self.generate_interactions()

        # Include manually-supplied interactions
        for variable, interaction in self.interactions.items():
            generated_interactions[variable] = interaction
        self.interactions = generated_interactions
        self.interaction_terms = [variable for variable in self.interactions] 

        # Handle importance calculation
        self.bucket_importances = {}
        self.bucket_importances['constant'] = [1 if var in self.important_variables else 0 for var in self.cols]
        self.bucket_importances['scaled'] = [max(abs(self.effects[var](0)), abs(self.effects[var](1))) if var in self.important_variables else 0 for var in self.cols]
        #self.bucket_importances['scaled_raw'] = [max(self.effects[var](0), self.effects[var](1), key=abs) if var in self.important_variables else 0 for var in self.cols]

        #not implemented yet
        #self.bucket_importances['sobol'] = [max(self.effects[var](0), self.effects[var](1), key=abs) if var in self.important_variables else 0 for var in self.cols]

        self.importances = [1 if var in self.important_variables else 0 for var in self.cols]

        if importance_ranking == 'constant':
            self.importances = self.bucket_importances['constant']
        elif importance_ranking == 'scaled':
            self.importances = self.bucket_importances['scaled']
        #elif importance_ranking == 'sobol':
        #    self.importances = self.bucket_importances['sobol']
        else:
            raise ValueError("importance_ranking must be 'constant', 'quick', or 'sobol'")
    
    def random_interaction(self, interacting_variables, cols=None, functions=None, monotonic=None):
        """
        Generate random interaction effects for specified columns.

        Parameters:
        - interacting_variables (list-like): List of columns to apply interactions.
        - cols (list-like, optional): List of all columns (default is self.cols).
        - functions (list-like, optional): List of functions to apply for interactions (default is self.functions).
        - monotonic (bool, optional): Whether interactions are monotonic (default is self.monotonic).

        Returns:
        - list: List of interaction effects for each column.
        """
        # Set class values if parameters None
        cols = cols if cols is not None else self.cols
        functions = functions if functions is not None else self.functions
        monotonic = monotonic if monotonic is not None else self.monotonic

        interaction_list = [lambda x: 0 for col in cols]

        random.seed(self.rng_seed)
        for col in interacting_variables:
            # Generate random values
            roll = random.choice(range(len(functions)))
            n = random.randint(1, DataGenerator.EFFECT_EXPONENT_RANGE)
            c = random.randint(1, DataGenerator.EFFECT_SCALE_RANGE)
            i = random.randint(0, 1)
            sign = random.choice([-1, 1])
            if monotonic:
                sign = 1

            f = lambda x, roll=roll, n=n, c=c, i=i, sign=sign: functions[roll](x, sign=sign, c=c, n=n, i=i)

            interaction_list[col] = f

        return interaction_list

    def generate_interactions(self, 
                              cols=None, 
                              interaction_terms=None, 
                              important_variables=None, 
                              scale=None, 
                              distribution=None):
        """
        Generate interaction terms between columns.

        Parameters:
        - cols (list-like, optional): List of all columns (default is self.cols).
        - interaction_terms (list-like, optional): List of columns to be used for interaction terms 
            (default is self.interaction_terms).
        - important_variables (list-like, optional): List of important columns (default is self.important_variables).
        - scale (float, optional): Scale of correlation for interactions (default is self.correlation_scale).
        - distribution (str, optional): Distribution type for correlations ('normal', 'uniform', 'beta') (default is self.correlation_distribution).

        Returns:
        - dict: Dictionary of interaction terms with corresponding columns and correlations.
        """
        # Set class values if parameters None
        cols = cols if cols is not None else self.cols
        interaction_terms = interaction_terms if interaction_terms is not None else self.interaction_terms
        important_variables = important_variables if important_variables is not None else self.important_variables
        scale = scale if scale is not None else self.correlation_scale
        distribution = distribution if distribution is not None else self.correlation_distribution

        interactions = {}
        rng = self.rng

        # Get random columns to interact with
        for term in interaction_terms:
            mimicking = rng.choice(important_variables)

            correlation = 0

            if distribution == 'uniform':
                correlation = rng.uniform(-scale, scale)
            elif distribution == 'normal':
                correlation = rng.normal(scale=scale)
            elif distribution == 'beta':
                correlation = rng.beta(scale, scale)
            else:
                raise ValueError("Unsupported distribution. Choose from 'uniform' or 'normal' or 'beta'.")
            
            correlation = max(-1, min(1, correlation))
            interactions[term] = (mimicking, correlation)

        return interactions
    
    def generate_noise(self, size=None, distribution=None, scale=None):
        """
        Generate noise for the dataset.

        Parameters:
        - size (int, optional): Number of noise samples to generate. (default is self.num_rows)
        - distribution (str, optional): Distribution type for noise ('normal', 'uniform', 'gamma') 
            (default is self.noise_distribution).
        - scale (float, optional): Scale of the noise (default is self.noise_scale).

        Returns:
        - np.ndarray: Array of noise values.
        """

        # Set defaults
        size = self.num_rows if size is None else size
        distribution = self.noise_distribution if distribution is None else distribution
        scale = self.noise_scale if scale is None else scale

        rng = self.rng

        if scale == 0:
            noise = np.zeros(size)  # If scale is zero, return an array of zeros
        elif distribution == 'uniform':
            noise = rng.uniform(-scale, scale, size=size)
        elif distribution == 'normal':
            noise = rng.normal(scale=scale, size=size)
        elif distribution == 'gamma':
            noise = rng.gamma(scale, size=size)
        else:
            raise ValueError("Unsupported distribution. Choose from 'uniform', 'normal', or 'gamma'.")

        return noise
    
    def predict(self, X, effects=None, target=None):
        """
        Predict the target variable based on input features and effects.

        Parameters:
        - X (pd.DataFrame): Input feature matrix.
        - effects (list, optional): List of effect functions for each column (default is self.effects).
        - target (str, optional): Name of the target column (default is self.target).

        Returns:
        - pd.Series: Predicted target values.
        """
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        X = X.astype(int)

        effects = effects if effects is not None else self.effects
        target = target if target is not None else self.target

        return sum(X[col].apply(effects[col]) for col in X.columns if col != target)
    
    def generate_data(self, num_rows=None, cols=None, frequencies=None, effects=None, interactions=None, target=None, intercept=None, noise_distribution=None, noise_scale=None):
        """
        Generates a dataset with binary columns, interaction terms, noise, and a target variable.

        Parameters:
        - num_rows (int, optional): Number of rows in the dataset (default is self.num_rows).
        - cols (list-like, optional): List of columns/features in the dataset (default is self.cols).
        - frequencies (dict-like, optional): Frequencies of 1s in binary columns (default is self.frequencies).
        - effects (list-like, optional): List of effect functions for each column (default is self.effects).
        - interactions (dict-like, optional): Dictionary of interaction terms (default is self.interactions).
        - target (str, optional): Name of the target column (default is self.target).
        - intercept (float, optional): Intercept for the target variable (default is self.intercept).
        - noise_distribution (str, optional): Distribution type for noise ('normal', 'uniform', 'gamma') 
            (default is self.noise_distribution).
        - noise_scale (float, optional): Scale of the noise (default is self.noise_scale).

        Returns:
        - pd.DataFrame: Generated dataset.

        This function allows for the simulation of datasets with specified properties, including
        predefined effects for certain columns, variable frequencies, interactions between variables,
        and a range of noise to simulate real-world data variance.
        """

        # Set defaults
        num_rows = num_rows if num_rows is not None else self.num_rows
        cols = cols if cols is not None else self.cols
        frequencies = frequencies if frequencies is not None else self.frequencies
        effects = effects if effects is not None else self.effects
        interactions = interactions if interactions is not None else self.interactions
        target = target if target is not None else self.target
        intercept = intercept if intercept is not None else self.intercept
        noise_scale = noise_scale if noise_scale is not None else self.noise_scale
        noise_distribution = noise_distribution if noise_distribution is not None else self.noise_distribution

        rng = self.rng
        data = {}

        # Generate data for each column
        for col in cols:
            freq = frequencies[col]
            data[col] = rng.choice([0, 1], size=num_rows, p=[1-freq, freq])
            
        df = pd.DataFrame(data)

        # Generate interactions
        random.seed(self.rng_seed)
        for col in interactions.keys():
            mimicking, correlation = interactions[col]

            df[col] = df.apply(lambda row: (1 - row[mimicking]) if (random.uniform(0, 1) < abs(correlation) and correlation < 0) 
                    else (row[mimicking] if (random.uniform(0, 1) < abs(correlation) and correlation > 0) 
                        else row[col]), 
            axis=1)
            df[col] = df[col].astype(int)
        
        df = df.copy()

        important_sum = self.predict(df)
        
        noise = self.generate_noise(scale=noise_scale * np.max(np.abs(important_sum)), distribution=noise_distribution, size=df.shape[0])

        # Generate target based on important cols, interactions, and non-linear effects
        df[target] = important_sum + noise + intercept

        return df