Benchmark data is not committed (144 MB). Download `creditcard.csv` from
https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud (ULB Machine Learning Group, ODbL) into this folder
(a copy without a Kaggle login: https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv), then:

    python benchmark/ulb_benchmark.py --csv data/creditcard.csv     # headline table
    python benchmark/ulb_robustness.py --csv data/creditcard.csv    # seeds, intervals, rolling windows
