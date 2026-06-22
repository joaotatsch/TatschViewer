# -*- coding: utf-8 -*-
from PyQt6.QtCore import QThread

class ThreadManager:
    """
    Gerenciador do ciclo de vida de QThreads para evitar Garbage Collection prematuro
    e encerramento sujo na aplicação.
    """
    def __init__(self, main_window):
        self.main_window = main_window
        self.active_threads = []
        self.threads_isoladas = []
        self.threads_prefetch = {}

    def cleanup_thread(self, thread):
        """Remove a thread da lista de ativas e das listas específicas quando termina, permitindo o GC apropriado."""
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        if thread in self.threads_isoladas:
            self.threads_isoladas.remove(thread)
        
        keys_to_remove = [k for k, v in self.threads_prefetch.items() if v == thread]
        for k in keys_to_remove:
            self.threads_prefetch.pop(k, None)

    def close_all(self):
        """Garante que todas as threads ativas sejam encerradas ou finalizadas corretamente ao fechar a aplicação."""
        todas_threads = list(self.active_threads) + list(self.threads_isoladas) + list(self.threads_prefetch.values())
        for thread in todas_threads:
            if isinstance(thread, QThread) and thread.isRunning():
                thread.quit()
                thread.wait()
