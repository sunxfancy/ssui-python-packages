"""Token streaming on the supported public Transformers generation API.

Retains the original package's init_stream_support, StreamGenerationConfig,
NewGenerationMixin and setup_seed entry points. Generation itself remains owned
by Transformers; no copied private sampling loop or removed output classes.
"""
from copy import deepcopy
from queue import Queue
import random
from threading import Event, Thread

import numpy as np
import torch
from transformers import GenerationConfig, GenerationMixin, PreTrainedModel
from transformers.generation.streamers import BaseStreamer
from transformers.generation.stopping_criteria import StoppingCriteria, StoppingCriteriaList

_GENERATE = GenerationMixin.generate


def setup_seed(seed):
    if seed is None or seed == -1:
        return
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class StreamGenerationConfig(GenerationConfig):
    def __init__(self, **kwargs):
        stream = kwargs.pop('do_stream', False)
        super().__init__(**kwargs)
        self.do_stream = stream


class _Cancelled(StoppingCriteria):
    def __init__(self, event):
        self.event = event

    def __call__(self, input_ids, scores, **kwargs):
        return torch.full((input_ids.shape[0],), self.event.is_set(), dtype=torch.bool, device=input_ids.device)


class _TokenStreamer(BaseStreamer):
    def __init__(self, queue):
        self.queue = queue
        self.prompt = True

    def put(self, value):
        if self.prompt:
            self.prompt = False
            return
        self.queue.put(('token', value.detach().clone()))

    def end(self):
        # Completion is signalled by the worker after generate() returns, so an
        # exception after end() cannot disappear behind a premature sentinel.
        pass


def _stream_tokens(model, args, kwargs):
    queue, cancelled = Queue(), Event()
    stopping = StoppingCriteriaList(list(kwargs.pop('stopping_criteria', None) or []))
    stopping.append(_Cancelled(cancelled))
    kwargs['stopping_criteria'] = stopping
    kwargs['streamer'] = _TokenStreamer(queue)

    def generate():
        try:
            _GENERATE(model, *args, **kwargs)
        except BaseException as error:
            queue.put(('error', error))
        finally:
            queue.put(('done', None))

    worker = Thread(target=generate, name='ssui-token-stream', daemon=True)
    worker.start()
    try:
        while True:
            kind, value = queue.get()
            if kind == 'done':
                break
            if kind == 'error':
                raise value
            yield value
    finally:
        cancelled.set()
        worker.join(timeout=30)
        if worker.is_alive():
            raise RuntimeError('Generation did not stop within 30 seconds after stream cancellation')


class NewGenerationMixin(GenerationMixin):
    def generate(self, *args, do_stream=None, seed=None, **kwargs):
        config = kwargs.get('generation_config') or self.generation_config
        stream = getattr(config, 'do_stream', False) if do_stream is None else do_stream
        if hasattr(config, 'do_stream'):
            config = deepcopy(config)
            delattr(config, 'do_stream')
            kwargs['generation_config'] = config
        setup_seed(seed)
        if not stream:
            return _GENERATE(self, *args, **kwargs)
        if kwargs.get('streamer') is not None:
            raise ValueError('do_stream owns the token streamer; do not supply another streamer')
        if kwargs.get('num_beams', config.num_beams) != 1:
            raise ValueError('Token streaming supports greedy and sampling generation with num_beams=1')
        return _stream_tokens(self, args, kwargs)

    def sample_stream(self, input_ids, **kwargs):
        kwargs['do_stream'] = True
        return NewGenerationMixin.generate(self, input_ids, **kwargs)


def init_stream_support():
    """Install the original package's opt-in, idempotent model entry points."""
    PreTrainedModel.generate = NewGenerationMixin.generate
    PreTrainedModel.sample_stream = NewGenerationMixin.sample_stream
