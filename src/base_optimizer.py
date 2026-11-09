from abc import ABC, abstractmethod
from typing import Dict, List, Any
from .data_classes import BaseOptimizerConfig, GeneticAlgorithmLookups, FormatterSettings # Updated import

class BaseOptimizer(ABC):
    """
    Abstract base class for clang-format configuration optimizers.
    Defines the interface for different optimization strategies.
    """
    def __init__(self, config: BaseOptimizerConfig):
        self.config = config

    @abstractmethod
    def optimize(self,
                 base_options_info: Dict[str, Any],
                 repo_paths: List[str],
                 lookups: GeneticAlgorithmLookups,
                 formatter_settings: FormatterSettings) -> Dict[str, Any]:
        """
        Abstract method to optimize clang-format configuration.

        Args:
            base_options_info (dict): The initial flat dictionary from clang-format --dump-config.
            repo_paths (list): A list of paths to the temporary git repositories for parallel processing.
            lookups (GeneticAlgorithmLookups): A dataclass containing lookup dictionaries for
                                               option values and forced options.
            formatter_settings (FormatterSettings): Settings of each fitness evaluation
                                                    (file sampling and its random seed).

        Returns:
            dict: The flat dictionary of the best clang-format configuration found.
        """
        pass
