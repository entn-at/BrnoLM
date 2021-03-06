#!/usr/bin/env python3
import argparse
import torch
import time

from safe_gpu.safe_gpu import GPUOwner

from brnolm.language_models import decoders


def str_time(dur):
    return f'{dur*1000.0:.2f} ms'


def measure_decoder(name, decoder, x, t, nb_measurements):
    decoder.train()
    # heating up, allocating memory etc.
    loss, nb_tokens = decoder.neg_log_prob(x, t)
    loss.backward()

    fwd_times = []
    bwd_times = []
    total_times = []
    total_loss = 0.0
    for _ in range(nb_measurements):
        t0 = time.time()
        loss, nb_tokens = decoder.neg_log_prob(x, t)
        t1 = time.time()
        loss.backward()
        t2 = time.time()
        total_loss += loss.item() / nb_tokens
        fwd_times.append(t1 - t0)
        bwd_times.append(t2 - t1)
        total_times.append(t2 - t0)
    print(f'{name} train: loss: {total_loss/nb_measurements:.2f}, fwd {str_time(min(fwd_times))}, bwd {str_time(min(bwd_times))}, total {str_time(min(total_times))} (avg total: {str_time(sum(total_times)/len(total_times))})')

    decoder.eval()
    # heating up, allocating memory etc.
    loss, nb_tokens = decoder.neg_log_prob(x, t)
    loss.backward()

    test_times = []
    test_loss = 0.0
    with torch.no_grad():
        for _ in range(nb_measurements):
            t0 = time.time()
            loss, nb_tokens = decoder.neg_log_prob(x, t)
            t1 = time.time()
            test_times.append(t1-t0)
            test_loss += loss.item() / nb_tokens
    print(f'{name} test: loss: {test_loss/nb_measurements:.2f}, total {str_time(min(test_times))} (avg total: {str_time(sum(test_times)/len(test_times))})')


def main(args):
    device = torch.device('cuda') if args.cuda else torch.device('cpu')
    lm_dense_output = torch.randn((args.total_batch_size, args.lm_dim), dtype=torch.float32, device=device)
    targets = torch.randint(0, args.vocab_size, (args.total_batch_size,), device=device)

    decoders_under_test = [
        ('full softmax', decoders.CustomLossFullSoftmaxDecoder(args.lm_dim, args.vocab_size)),
        ('full softmax+ls', decoders.CustomLossFullSoftmaxDecoder(args.lm_dim, args.vocab_size, label_smoothing=0.1)),
    ]

    for name, decoder in decoders_under_test:
        measure_decoder(name, decoder.to(device), lm_dense_output, targets, args.nb_measurements)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--total-batch-size', type=int, required=True)
    parser.add_argument('--lm-dim', type=int, required=True)
    parser.add_argument('--vocab-size', type=int, required=True)
    parser.add_argument('--nb-measurements', type=int, default=3)
    parser.add_argument('--cuda', action='store_true')
    args = parser.parse_args()

    if args.cuda:
        gpu_owner = GPUOwner()

    main(args)
