"""Apply a graph convolutionally to datapoints in an biggie file."""

import argparse
import numpy as np
import json
import biggie
import os
import marl.fileutils as futil
import time

import dl4mir.common.util as util
import scipy.signal as signal


def mle(posterior):
    return posterior.argmax(axis=1)


def medfilt_mle(posterior, shape=[41, 1]):
    return mle(signal.medfilt(posterior, shape))


def viterbi(posterior, penalty):
    # TODO: this is unnecessary now.
    transmat = np.ones([posterior.shape[1]] * 2)
    return util.viterbi(posterior, transmat, penalty=penalty)


def estimate_classes(entity, prediction_fx, **kwargs):
    """

    Parameters
    ----------
    posterior: np.ndarray
        Posteriorgram of chord classes.
    viterbi_penalty: scalar, in (0, inf)
        Self-transition penalty; higher values produce more "stable" paths.

    Returns
    -------
    estimations: dict
        Chord labels and dense count vectors.
    """
    num_classes = entity.posterior.shape[1]
    estimations = dict()
    y_pred = prediction_fx(entity.posterior, **kwargs)
    if hasattr(entity, 'durations'):
        weights = np.asarray(entity.durations)
    else:
        weights = np.ones(len(y_pred))
    for label, idx, w in zip(entity.chord_labels, y_pred, weights):
        if not label in estimations:
            estimations[label] = np.zeros(num_classes, dtype=np.int).tolist()
        estimations[label][idx] += w

    return estimations


PRED_FXS = dict(mle=mle, medfilt_mle=medfilt_mle, viterbi=viterbi)


def process_one(stash, key, idx, prediction_fx, **kwargs):
    estimations = estimate_classes(stash.get(key), prediction_fx, **kwargs)
    print "[%s] %12d / %12d: %s" % (time.asctime(), idx, len(stash), key)
    return key, estimations


def main(args):
    if not os.path.exists(args.posterior_file):
        print "File does not exist: %s" % args.posterior_file
        return
    dset = biggie.Stash(args.posterior_file)
    stats = json.load(open(args.validation_file))
    penalty = float(stats['best_config']['penalty'])
    fx = PRED_FXS.get('viterbi')
    estimations = dict()
    for idx, key in enumerate(dset.keys()):
        estimations[key] = estimate_classes(dset.get(key), fx, penalty=penalty)
        print "[%s] %12d / %12d: %s" % (time.asctime(), idx, len(dset), key)

    futil.create_directory(os.path.split(args.estimation_file)[0])
    with open(args.estimation_file, 'w') as fp:
        json.dump(estimations, fp, indent=2)

    futil.create_directory(os.path.split(args.estimation_file)[0])
    with open(args.estimation_file, 'w') as fp:
        json.dump(estimations, fp, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")

    # Inputs
    parser.add_argument("posterior_file",
                        metavar="posterior_file", type=str,
                        help="Path to an optimus file of chord posteriors.")
    parser.add_argument("validation_file",
                        metavar="validation_file", type=str,
                        help="")
    # Outputs
    parser.add_argument("estimation_file",
                        metavar="estimation_file", type=str,
                        help="Path for the lab-file style output as JSON.")
    main(parser.parse_args())
