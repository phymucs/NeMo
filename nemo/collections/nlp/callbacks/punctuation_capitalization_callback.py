# =============================================================================
# Copyright 2020 NVIDIA. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

import random

import numpy as np
from sklearn.metrics import classification_report

from nemo import logging
from nemo.collections.nlp.utils.callback_utils import list2str, plot_confusion_matrix, tensor2list

__all__ = ['eval_iter_callback', 'eval_epochs_done_callback']


def eval_iter_callback(tensors, global_vars):
    if "punct_all_preds" not in global_vars.keys():
        global_vars["punct_all_preds"] = []
    if "punct_all_labels" not in global_vars.keys():
        global_vars["punct_all_labels"] = []
    if "capit_all_preds" not in global_vars.keys():
        global_vars["capit_all_preds"] = []
    if "capit_all_labels" not in global_vars.keys():
        global_vars["capit_all_labels"] = []
    if "all_subtokens_mask" not in global_vars.keys():
        global_vars["all_subtokens_mask"] = []

    all_subtokens_mask = []
    punct_all_logits, punct_all_labels = [], []
    capit_all_logits, capit_all_labels = [], []

    for kv, v in tensors.items():
        if 'Punctuation' in kv and 'logits' in kv:
            for v_tensor in v:
                for logit_tensor in v_tensor:
                    punct_all_logits.append(tensor2list(logit_tensor))

        elif kv.startswith('punct_labels'):
            for v_tensor in v:
                for label_tensor in v_tensor:
                    punct_all_labels.extend(tensor2list(label_tensor))

        elif 'Capitalization' in kv and 'logits' in kv:
            for v_tensor in v:
                for logit_tensor in v_tensor:
                    capit_all_logits.append(tensor2list(logit_tensor))

        elif kv.startswith('capit_labels'):
            for v_tensor in v:
                for label_tensor in v_tensor:
                    capit_all_labels.extend(tensor2list(label_tensor))

        elif kv.startswith('subtokens_mask'):
            for v_tensor in v:
                for subtokens_mask_tensor in v_tensor:
                    all_subtokens_mask.extend(tensor2list(subtokens_mask_tensor))

    punct_all_preds = list(np.argmax(np.asarray(punct_all_logits), 2).flatten())
    global_vars["punct_all_preds"].extend(punct_all_preds)
    global_vars["punct_all_labels"].extend(punct_all_labels)

    capit_all_preds = list(np.argmax(np.asarray(capit_all_logits), 2).flatten())
    global_vars["capit_all_preds"].extend(capit_all_preds)
    global_vars["capit_all_labels"].extend(capit_all_labels)

    global_vars["all_subtokens_mask"].extend(all_subtokens_mask)


def eval_epochs_done_callback(global_vars, punct_label_ids, capit_label_ids, graph_fold=None, normalize_cm=True):
    '''
    Args:
      graph_fold (str): path to output folder
      normalize_cm (bool): flag to indicate whether to
        normalize confusion matrix
    '''

    punct_accuracy = _eval_epochs_done_callback('punct', global_vars, punct_label_ids, graph_fold, normalize_cm)

    capit_accuracy = _eval_epochs_done_callback('capit', global_vars, capit_label_ids, graph_fold, normalize_cm)

    return {"Punctuation_task_accuracy": punct_accuracy, "Capitalization_task_accuracy": capit_accuracy}


def _eval_epochs_done_callback(task_name, global_vars, label_ids, graph_fold=None, normalize_cm=True):
    labels = np.asarray(global_vars[task_name + '_all_labels'])
    preds = np.asarray(global_vars[task_name + '_all_preds'])
    subtokens_mask = np.asarray(global_vars['all_subtokens_mask']) > 0.5

    labels = labels[subtokens_mask]
    preds = preds[subtokens_mask]

    accuracy = sum(labels == preds) / labels.shape[0]
    logging.info(f'Accuracy for task {task_name}: {accuracy}')

    # print predictions and labels for a small random subset of data
    sample_size = 20
    i = 0
    if preds.shape[0] > sample_size + 1:
        i = random.randint(0, preds.shape[0] - sample_size - 1)
    logging.info("Sampled preds: [%s]" % list2str(preds[i : i + sample_size]))
    logging.info("Sampled labels: [%s]" % list2str(labels[i : i + sample_size]))

    # remove labels from label_ids that don't appear in the dev set
    used_labels = set(labels) | set(preds)
    label_ids = {k: label_ids[k] for k, v in label_ids.items() if v in used_labels}

    logging.info(classification_report(labels, preds, target_names=label_ids))

    # calculate and plot confusion_matrix
    if graph_fold:
        plot_confusion_matrix(labels, preds, graph_fold, label_ids, normalize=normalize_cm, prefix=task_name)
    return accuracy
