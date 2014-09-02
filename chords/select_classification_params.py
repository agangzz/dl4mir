import argparse
import numpy as np
import marl.fileutils as futils
import optimus
import biggie
import time
import sklearn.metrics as metrics
from scipy import signal

from os import path
import shutil

import dl4mir.chords.data as D
import dl4mir.common.streams as S

POSTERIOR = 'posterior'


def average_prf(batches, predictor):
    y_true, y_pred = [], []
    for data in batches:
        y_true.append(data['chord_idx'])
        y_pred.append(predictor(data['cqt'])[POSTERIOR].argmax(axis=1))
    y_true = np.concatenate(y_true)
    y_pred = np.concatenate(y_pred)
    return [metrics.precision_score(y_true, y_pred),
            metrics.recall_score(y_true, y_pred),
            metrics.f1_score(y_true, y_pred)]


def find_best_param_file(param_files, predictor, stream, num_obs,
                         metric='recall', filt_len=5, start_idx=0):
    """TODO(ejhumphrey): could save the scores, in case they're needed again...
    """
    score_idx = dict(precision=0, recall=1, f1=2)[metric]
    best_score = -np.inf
    best_param_file = ''
    param_files.sort()
    param_files = param_files[start_idx:]
    all_scores = []
    batches = [stream.next() for _ in range(num_obs)]
    try:
        for idx, pf in enumerate(param_files):
            key = path.split(pf)[-1]
            np.load(pf)
            predictor.param_values = np.load(pf)
            scores = average_prf(batches, predictor)
            all_scores.append(scores[score_idx])
            score_str = "/".join(["%0.4f" % v for v in scores])
            print "[%s] %4d: (%s) %s" % (time.asctime(), idx, score_str, key)
            # if score > best_score:
            #     best_score = score
            #     best_param_file = pf
            #     print " >>> New best: %0.4f @ %s" % (best_score, key)
    except KeyboardInterrupt:
        print "Stopping early"

    w_n = np.hanning(filt_len)
    w_n /= np.sum(w_n)
    if len(all_scores) > 15:
        smoothed = signal.filtfilt(w_n, np.ones(1), np.array(all_scores))
        best_idx = smoothed.argmax()
    else:
        best_idx = np.array(all_scores).argmax()
    return param_files[best_idx]


def main(args):
    predictor = optimus.load(args.transform_file)
    time_dim = predictor.inputs.values()[0].shape[2]

    stash = biggie.Stash(args.data_file)
    stream = S.minibatch(
        D.create_chord_stream(stash, time_dim, pitch_shift=0),
        batch_size=200)

    best_params = find_best_param_file(
        param_files=futils.load_textlist(args.param_textlist),
        stream=stream,
        predictor=predictor,
        num_obs=args.num_obs,
        start_idx=args.start_idx)

    shutil.copyfile(best_params, args.param_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")

    # Inputs
    parser.add_argument("data_file",
                        metavar="data_file", type=str,
                        help="Path to an optimus file for validation.")
    parser.add_argument("transform_file",
                        metavar="transform_file", type=str,
                        help="Validator graph definition.")
    parser.add_argument("param_textlist",
                        metavar="param_textlist", type=str,
                        help="Path to save the training results.")
    parser.add_argument("--num_obs",
                        metavar="--num_obs", type=int, default=100,
                        help="Number of observations per parameter set.")
    parser.add_argument("--start_idx",
                        metavar="--start_idx", type=int, default=0,
                        help="Index of the parameter file to start with.")
    # Outputs
    parser.add_argument("param_file",
                        metavar="param_file", type=str,
                        help="Path for renaming best parameters.")
    main(parser.parse_args())