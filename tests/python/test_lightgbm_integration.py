# -*- coding: utf-8 -*-
"""Tests for LightGBM integration"""
import os

import numpy as np
import scipy.sparse
import pytest
import treelite
import treelite_runtime
from treelite.contrib import _libext
from treelite.util import has_sklearn
from .metadata import dataset_db, _qualify_path
from .util import os_compatible_toolchains, os_platform, check_predictor

try:
    import lightgbm
except ImportError:
    # skip this test suite if LightGBM is not installed
    pytest.skip('LightGBM not installed; skipping', allow_module_level=True)


@pytest.mark.skipif(not has_sklearn(), reason='Needs scikit-learn')
@pytest.mark.parametrize('toolchain', os_compatible_toolchains())
@pytest.mark.parametrize('objective', ['regression', 'regression_l1', 'huber'])
@pytest.mark.parametrize('reg_sqrt', [True, False])
def test_lightgbm_regression(tmpdir, objective, reg_sqrt, toolchain):
    # pylint: disable=too-many-locals
    """Test a regressor"""
    model_path = os.path.join(tmpdir, 'boston_lightgbm.txt')

    from sklearn.datasets import load_boston
    from sklearn.model_selection import train_test_split

    X, y = load_boston(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    dtrain = lightgbm.Dataset(X_train, y_train, free_raw_data=False)
    dtest = lightgbm.Dataset(X_test, y_test, reference=dtrain, free_raw_data=False)
    param = {'task': 'train', 'boosting_type': 'gbdt', 'objective': objective, 'reg_sqrt': reg_sqrt,
             'metric': 'rmse', 'num_leaves': 31, 'learning_rate': 0.05}
    bst = lightgbm.train(param, dtrain, num_boost_round=10, valid_sets=[dtrain, dtest],
                         valid_names=['train', 'test'])
    bst.save_model(model_path)

    model = treelite.Model.load(model_path, model_format='lightgbm')
    libpath = os.path.join(tmpdir, f'boston_{objective}' + _libext())
    model.export_lib(toolchain=toolchain, libpath=libpath, params={'quantize': 1}, verbose=True)
    predictor = treelite_runtime.Predictor(libpath=libpath, verbose=True)

    dmat = treelite_runtime.DMatrix(X_test, dtype='float64')
    out_pred = predictor.predict(dmat)
    expected_pred = bst.predict(X_test)
    np.testing.assert_almost_equal(out_pred, expected_pred, decimal=5)


@pytest.mark.skipif(not has_sklearn(), reason='Needs scikit-learn')
@pytest.mark.parametrize('toolchain', os_compatible_toolchains())
@pytest.mark.parametrize('boosting_type', ['gbdt', 'rf'])
@pytest.mark.parametrize('objective', ['multiclass', 'multiclassova'])
def test_lightgbm_multiclass_classification(tmpdir, objective, boosting_type, toolchain):
    # pylint: disable=too-many-locals
    """Test a multi-class classifier"""
    model_path = os.path.join(tmpdir, 'iris_lightgbm.txt')

    from sklearn.datasets import load_iris
    from sklearn.model_selection import train_test_split

    X, y = load_iris(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    dtrain = lightgbm.Dataset(X_train, y_train, free_raw_data=False)
    dtest = lightgbm.Dataset(X_test, y_test, reference=dtrain, free_raw_data=False)
    param = {'task': 'train', 'boosting': boosting_type, 'objective': objective,
             'metric': 'multi_logloss', 'num_class': 3, 'num_leaves': 31, 'learning_rate': 0.05}
    if boosting_type == 'rf':
        param.update({'bagging_fraction': 0.8, 'bagging_freq': 1})
    bst = lightgbm.train(param, dtrain, num_boost_round=10, valid_sets=[dtrain, dtest],
                         valid_names=['train', 'test'])
    bst.save_model(model_path)

    model = treelite.Model.load(model_path, model_format='lightgbm')
    libpath = os.path.join(tmpdir, f'iris_{objective}' + _libext())
    model.export_lib(toolchain=toolchain, libpath=libpath, params={'quantize': 1}, verbose=True)
    predictor = treelite_runtime.Predictor(libpath=libpath, verbose=True)

    dmat = treelite_runtime.DMatrix(X_test, dtype='float64')
    out_pred = predictor.predict(dmat)
    expected_pred = bst.predict(X_test)
    np.testing.assert_almost_equal(out_pred, expected_pred, decimal=5)


@pytest.mark.parametrize('toolchain', os_compatible_toolchains())
@pytest.mark.parametrize('objective', ['binary', 'xentlambda', 'xentropy'])
def test_lightgbm_binary_classification(tmpdir, objective, toolchain):
    # pylint: disable=too-many-locals
    """Test a binary classifier"""
    dataset = 'mushroom'
    model_path = os.path.join(tmpdir, 'mushroom_lightgbm.txt')
    dtest_path = dataset_db[dataset].dtest

    dtrain = lightgbm.Dataset(dataset_db[dataset].dtrain)
    dtest = lightgbm.Dataset(dtest_path, reference=dtrain)
    param = {'task': 'train', 'boosting_type': 'gbdt', 'objective': objective, 'metric': 'auc',
             'num_leaves': 7, 'learning_rate': 0.1}
    bst = lightgbm.train(param, dtrain, num_boost_round=10, valid_sets=[dtrain, dtest],
                         valid_names=['train', 'test'])
    bst.save_model(model_path)

    expected_prob = bst.predict(dtest_path)
    expected_margin = bst.predict(dtest_path, raw_score=True)

    model = treelite.Model.load(model_path, model_format='lightgbm')
    libpath = os.path.join(tmpdir, f'agaricus_{objective}' + _libext())
    dmat = treelite_runtime.DMatrix(dtest_path, dtype='float64')
    model.export_lib(toolchain=toolchain, libpath=libpath, params={}, verbose=True)
    predictor = treelite_runtime.Predictor(libpath, verbose=True)
    out_prob = predictor.predict(dmat)
    np.testing.assert_almost_equal(out_prob, expected_prob, decimal=5)
    out_margin = predictor.predict(dmat, pred_margin=True)
    np.testing.assert_almost_equal(out_margin, expected_margin, decimal=5)


@pytest.mark.parametrize('toolchain', os_compatible_toolchains())
@pytest.mark.parametrize('parallel_comp', [None, 2])
@pytest.mark.parametrize('quantize', [True, False])
def test_categorical_data(tmpdir, quantize, parallel_comp, toolchain):
    """
    LightGBM is able to produce categorical splits directly, so that
    categorical data don't have to be one-hot encoded. Test if Treelite is
    able to handle categorical splits.

    This toy example contains two features, both of which are categorical.
    The first has cardinality 3 and the second 5. The label was generated using
    the formula

       y = f(x0) + g(x1) + [noise with std=0.1]

    where f and g are given by the tables

       x0  f(x0)        x1  g(x1)
        0    -20         0     -2
        1    -10         1     -1
        2      0         2      0
                         3      1
                         4      2
    """
    dataset = 'toy_categorical'
    libpath = os.path.join(tmpdir, dataset_db[dataset].libname + _libext())
    model = treelite.Model.load(dataset_db[dataset].model, model_format=dataset_db[dataset].format)

    params = {
        'quantize': (1 if quantize else 0),
        'parallel_comp': (parallel_comp if parallel_comp else 0)
    }
    model.export_lib(toolchain=toolchain, libpath=libpath, params=params, verbose=True)
    predictor = treelite_runtime.Predictor(libpath=libpath, verbose=True)
    check_predictor(predictor, dataset)


@pytest.mark.parametrize('toolchain', os_compatible_toolchains())
@pytest.mark.parametrize('quantize', [True, False])
def test_sparse_ranking_model(tmpdir, quantize, toolchain):
    # pylint: disable=too-many-locals
    """Generate a LightGBM ranking model with highly sparse data.
    This example is inspired by https://github.com/dmlc/treelite/issues/222. It verifies that
    Treelite is able to accommodate the unique behavior of LightGBM when it comes to handling
    missing values.

    LightGBM offers two modes of handling missing values:

    1. Assign default direction per each test node: This is similar to how XGBoost handles missing
       values.
    2. Replace missing values with zeroes (0.0): This behavior is unique to LightGBM.

    The mode is controlled by the missing_value_to_zero_ field of each test node.

    This example is crafted so as to invoke the second mode of missing value handling.
    """
    rng = np.random.default_rng(seed=2020)
    X = scipy.sparse.random(m=10, n=206947, format='csr', dtype=np.float64, random_state=0,
                            density=0.0001)
    X.data = rng.standard_normal(size=X.data.shape[0], dtype=np.float64)
    y = rng.integers(low=0, high=5, size=X.shape[0])

    params = {
        'objective': 'lambdarank',
        'num_leaves': 32,
        'lambda_l1': 0.0,
        'lambda_l2': 0.0,
        'min_gain_to_split': 0.0,
        'learning_rate': 1.0,
        'min_data_in_leaf': 1
    }

    model_path = os.path.join(tmpdir, 'sparse_ranking_lightgbm.txt')
    libpath = os.path.join(tmpdir, 'sparse_ranking_lgb' + _libext())

    dtrain = lightgbm.Dataset(X, label=y, group=[X.shape[0]])

    bst = lightgbm.train(params, dtrain, num_boost_round=1)
    lgb_out = bst.predict(X)
    bst.save_model(model_path)

    model = treelite.Model.load(model_path, model_format='lightgbm')
    params = {'quantize': (1 if quantize else 0)}
    model.export_lib(toolchain=toolchain, libpath=libpath, params=params, verbose=True)

    predictor = treelite_runtime.Predictor(libpath, verbose=True)

    dmat = treelite_runtime.DMatrix(X)
    out = predictor.predict(dmat)

    np.testing.assert_almost_equal(out, lgb_out)


@pytest.mark.parametrize('toolchain', os_compatible_toolchains())
@pytest.mark.parametrize('quantize', [True, False])
def test_sparse_categorical_model(tmpdir, quantize, toolchain):
    """
    LightGBM is able to produce categorical splits directly, so that
    categorical data don't have to be one-hot encoded. Test if Treelite is
    able to handle categorical splits.

    This example produces a model with high-cardinality categorical variables.
    The training data has many missing values, so we need to match LightGBM
    when it comes to handling missing values
    """
    if toolchain == 'clang':
        pytest.xfail(reason='Clang cannot handle long if conditional')
    if os_platform() == 'windows':
        pytest.xfail(reason='MSVC cannot handle long if conditional')
    if os_platform() == 'osx':
        pytest.xfail(reason='Apple Clang cannot handle long if conditional')
    dataset = 'sparse_categorical'
    libpath = os.path.join(tmpdir, dataset_db[dataset].libname + _libext())
    model = treelite.Model.load(dataset_db[dataset].model, model_format=dataset_db[dataset].format)
    params = {'quantize': (1 if quantize else 0)}
    model.export_lib(toolchain=toolchain, libpath=libpath, params=params, verbose=True,
                     options=['-O0'])
    predictor = treelite_runtime.Predictor(libpath=libpath, verbose=True)
    check_predictor(predictor, dataset)


def test_constant_tree():
    """Test whether Treelite can handle LightGBM models with a constant tree (which has a single
    node)"""
    model_path = _qualify_path('lightgbm_constant_tree', 'model_with_constant_tree.txt')
    model = treelite.Model.load(model_path, model_format='lightgbm')
    assert model.num_tree == 2
