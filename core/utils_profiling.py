# -*- coding: utf-8 -*-
import time
import functools
import os

def profiler_time(func):
    """
    Decorator de telemetria de precisão atômica usando perf_counter.
    Mede e imprime o tempo de execução no console para diagnóstico de gargalos.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        delta = end_time - start_time
        
        try:
            # Tenta pegar o nome do arquivo de onde a função vem
            file_path = func.__code__.co_filename
            module_name = os.path.basename(file_path)
        except AttributeError:
            module_name = "UnknownModule"
            
        print(f"[PROFILING] {module_name} -> {func.__qualname__}: {delta:.4f} segundos.")
        return result
    return wrapper
