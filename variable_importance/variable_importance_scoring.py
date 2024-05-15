from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error
from scipy.stats import spearmanr
from variable_importance.cmr import CMR
from variable_importance.loco import LOCOImportance
from variable_importance.mr import MRImportance
import numpy as np
import shap
import warnings

def importance_score_estimator(estimator, X, y, true_importances=[], importance_attr='feature_importances_', score=spearmanr):
    warnings.filterwarnings("error")
    estimator.fit(X, y)
    try:
        pred_importances = getattr(estimator, importance_attr)
        correlation, _ = score(true_importances, pred_importances)
    except:
        correlation = 0
    finally:
        return correlation

def importance_score(pred_importances, true_importances=[], score=spearmanr):
    warnings.filterwarnings("error")
    try:
        correlation, _ = score(true_importances, pred_importances)
    except Exception as e:
        print(e)
        correlation = 0
    finally:
        return correlation

def model_importance_score(model, true_importances, importance_attr, score=spearmanr):
    pred_importances = list(getattr(model, importance_attr))
    return importance_score(pred_importances, true_importances=true_importances, score=score)


def cross_validation_scores(cv, X, y, test_size=0.2, importance_attr='feature_importances_', true_importances=[], score_function_names=['model_importance'], verbose=False):
    '''
    Present an initialized cross-validator such as GridSearchCV or RandomizedSearchCV
    '''
    scores = {}
    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)

    failed = False
    try:
        cv.fit(X_train, y_train)
    except Exception as e:
        #warnings.warn("something bad happened", UserWarning)
        scores['model'] = None
        scores['params'] = None
        scores['training_r2'] = None
        scores['test_r2'] = None
        for name in score_function_names:
            scores[name] = None

        failed = True
    finally:
        if failed:
            return scores
    
    best_model = cv.best_estimator_
    scores['model'] = best_model
    scores['params'] = cv.best_params_

    # Calculate predictions for the training set and the test set
    y_train_pred = best_model.predict(X_train)
    y_test_pred = best_model.predict(X_test)

    # Training and test R^2 score
    scores['training_r2'] = r2_score(y_train, y_train_pred)
    scores['test_r2'] = r2_score(y_test, y_test_pred)

    for name in score_function_names:
        if name == 'model_importance':
            scores[name] = model_importance_score(best_model, true_importances, importance_attr)
        elif name == 'cmr_importance':
            cmr = CMR(X_train, y_train, mean_squared_error, best_model)
            imp = cmr.importance_all()
            scores[name] = importance_score(imp, true_importances)
        elif name == 'loco_importance':
            loco = LOCOImportance(X_train, y_train, 'r2', best_model, cv=5)
            scores[name] = importance_score(loco.get_importance(), true_importances)
        elif name == 'mr_importance':
            mr = MRImportance(X_train, y_train, 'r2', best_model)
            scores[name] = importance_score(mr.get_importance(), true_importances)
        elif name == 'shap_importance':
            explainer = shap.Explainer(best_model, X_train)
            shap_values = explainer.shap_values(X_train)
            shap_avg = np.average(np.abs(shap_values), axis=0)
            scores[name] = importance_score(shap_avg, true_importances)

            
    if verbose:
        print(f"Scores For {best_model.__class__}")
        print(f"Training R^2 Score: {scores['training_r2']}")
        print(f"Test R^2 Score: {scores['test_r2']}")
        print("Importance Scores:")
        for name in score_function_names:
            print(f"{name}: {scores[name]}")

    return scores