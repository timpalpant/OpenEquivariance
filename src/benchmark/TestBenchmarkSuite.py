import json, os, time, pathlib

import numpy as np
from typing import NamedTuple, Optional, Iterable, Literal, Any, get_args
from dataclasses import dataclass

from src.implementations.TensorProduct import TensorProduct
from src.implementations.e3nn_lite import TPProblem

from src.benchmark.logging_utils import *
from build.kernel_wrapper import *
from src.implementations.e3nn_lite import *
from src.benchmark.correctness_utils import correctness_forward, correctness_backward
from src.benchmark.benchmark_utils import benchmark_forward, benchmark_backward

Direction = Literal['forward', 'backward']

class TestDefinition(NamedTuple):
    implementation : TensorProduct
    problem : TPProblem
    direction : Direction
    correctness : bool = True
    benchmark : bool = True

@dataclass(init=True, repr=False, eq=False)
class TestBenchmarkSuite:
    num_warmup : int = 10
    num_iter : int = 30
    correctness_batch_size : int = 10000
    bench_batch_size : int = 10000000
    prng_seed : int = 12345
    reference_implementation : Optional[type[TensorProduct]] = None
    correctness_threshold : float = 5e-7

    def validate_inputs(test_list : Iterable[TestDefinition]) -> None:
        """
        Just does empty list and type checking to catch bad input 
        """
        assert isinstance(test_list, list) 
        assert len(test_list) != 0
        for test in test_list:
            assert isinstance(test, TestDefinition)
            assert issubclass(test.implementation, TensorProduct)
            assert isinstance(test.problem, TPProblem)
            assert test.direction in get_args(Direction)
            assert isinstance(test.correctness, bool)
            assert isinstance(test.benchmark, bool)

    def generate_metadata(test_list : Iterable[TestDefinition]) -> dict[str, Any]:
        """
        creates an (incomplete) summary of what was tested
        """
       
        tpps, impls, directions, corectnesses, benchmarks = zip(*test_list)
        config_names = list(set(str(tpps)))
        implementation_names = list(set(str(impls.__class__.__name__)))
        directions = list(set(directions))
        did_correctness = any(corectnesses)
        did_benchmark = any(benchmarks)

        metadata = {
                "configs" : config_names,
                "implementations" : implementation_names,
                "directions" : directions,
                "did_correctness" :  did_correctness, 
                "did_benchmark" : did_benchmark,
            }
        
        test_details = {}
        for test_ID, test in enumerate(test_list):
            test_details[test_ID] = repr(test.problem)
        
        metadata['test details'] = test_details

        return metadata

    def run(self, test_list : Iterable[TestDefinition]):        
        
        TestBenchmarkSuite.validate_inputs(test_list)

        millis_since_epoch = round(time.time() * 1000)
        output_folder = pathlib.Path(f'outputs/{millis_since_epoch}')
        output_folder.mkdir(parents=True)

        metadata = TestBenchmarkSuite.generate_metadata(test_list)

        with open(os.path.join(output_folder,'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2) 

        for test_ID, test in enumerate(test_list): 
            impl = test.implementation
            tpp = test.problem

            logger.info(f'Starting Test ID: {test_ID}')
            logger.info(f'Config: {str(tpp)}')
            logger.info(f'Implementation Name: {impl.__name__}')
            logger.info(f'Test Direction: {test.direction}')

            result = {
                "config": repr(tpp),
                "direction": test.direction, 
                "implementation name": impl.__name__,
                "correctness": str(test.correctness),
                "benchmark": str(test.benchmark)
            }

            if test.direction == 'forward':
                if test.correctness:
                    result['correctness results'] = correctness_forward(
                        problem=tpp,
                        test_implementation=impl,
                        reference_implementation=self.reference_implementation,
                        batch_size=self.correctness_batch_size,
                        correctness_threshold=self.correctness_threshold,
                        prng_seed=self.prng_seed,
                    )
                if test.benchmark:
                    result['benchmark results'] = benchmark_forward(
                        problem=tpp,
                        implementation=impl,
                        batch_size=self.bench_batch_size,
                        num_warmup=self.num_warmup,
                        num_iter=self.num_iter,
                        prng_seed=self.prng_seed
                    )


            if test.direction == 'backward':
                pass 
                if test.correctness: 
                    result ['correctness results'] = correctness_backward(
                        problem=tpp,
                        test_implementation=impl,
                        reference_implementation=self.reference_implementation,
                        batch_size=self.correctness_batch_size,
                        prng_seed=self.prng_seed
                    )
                if test.benchmark: 
                    result ['benchmark results'] = benchmark_backward(
                        problem=tpp,
                        implementation=impl,
                        batch_size=self.bench_batch_size,
                        num_warmup=self.num_warmup,
                        num_iter=self.num_iter,
                        prng_seed=self.prng_seed
                    )
    
            fname = pathlib.Path(f"{output_folder}/{test_ID}.json")

            pretty_result = json.dumps(obj=result, indent=2).replace('\\n', '\n')
            logger.debug(pretty_result)
            with open(fname, 'w') as f:
                json.dump(result, f, indent=2)

            logger.info(f'Finished Test ID: {test_ID}')