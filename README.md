# Clang-Format Optimizer 🚀
This project provides a tool for quickly configuring `clang-format` to match the style of an existing codebase. In other words, it aims to find a `.clang-format` configuration that minimizes the number of changes (insertions + deletions) when applied to the codebase, thereby reducing formatting churn and improving code consistency.

## Features
*   **Genetic Algorithm Optimization** 🧬: Employs a genetic algorithm with an island model to explore a wide range of `clang-format` options and find an optimal configuration.
*   **Black-Box Optimization with Nevergrad** 📦: Integrates Nevergrad, a state-of-the-art black-box optimization library, offering alternative algorithms like CMA-ES, Differential Evolution, and more.
*   **Any `clang-format` Version** 🎯: Optimizes for the `clang-format` you choose (`--clang-format clang-format-20`), with the option values of that version (`get_option_values.py --llvm-version 20`). The best configuration depends on the version: the same configuration can change a different number of lines with `clang-format` 18 and 20.
*   **Start From Your `.clang-format`** 📄: Starts from an existing configuration, expanded to every option of the chosen `clang-format`, and can write the result back into that file, changing only the options that changed and keeping its comments and layout (`--update-start-config`).
*   **Forced Options** 🔒: Allows users to specify certain `clang-format` options that should always be set to a particular value, overriding the optimization process for those specific options.
*   **Change Minimization** 📊: The fitness of a configuration is the number of lines that `clang-format` changes in the repository (insertions + deletions of `git diff --shortstat`). Third-party and generated code can be left out (`--exclude`).
*   **Progress Display** ⏳: A progress bar with the generations or evaluations done, the evaluation rate, the best fitness and the remaining time; a short output by default, every evaluation with `--verbose`.
*   **Interactive Plotting** 📈: Optionally visualizes the best fitness score over time using `matplotlib` (`--plot-fitness`).
*   **Parallelization** ⚡: Utilizes multiple CPU cores by running fitness evaluations in parallel, each in its own temporary clone of the repository.
*   **File Sampling** ✂️: Speeds up optimization by evaluating a random sample of the files.
*   **Graceful Termination** 🛑: Supports `Ctrl-C` to stop the optimization and write the best configuration found so far.

## Installation
### Prerequisites 🛠️
*   **Python 3.9 or newer** 🐍, preferably with [uv](https://docs.astral.sh/uv/).
*   **clang-format**: the version your project formats with, from your system's package manager (e.g. `sudo apt install clang-format-20` on Ubuntu, `brew install llvm` on macOS) or any other source. It does not need to be the `clang-format` in `PATH`: pass it with `--clang-format`.
*   **Git**: the repository to analyze must be a git repository.

### Python Dependencies 📦
#### With uv (recommended)
`main.py`, `get_option_values.py` and `test.py` declare their dependencies as [PEP 723](https://peps.python.org/pep-0723/) inline script metadata. uv installs them into a cached environment on the first run, so there is no installation step:

```bash
uv run main.py <repo_path> [OPTIONS]
uv run get_option_values.py --llvm-version 20 > clang-format-20-values.json
```

#### With pip
1.  **Create a virtual environment (optional but recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate # On Windows: venv\Scripts\activate
    ```
2.  **Install the required Python packages:**
    ```bash
    pip install ruamel.yaml requests beautifulsoup4 lxml matplotlib nevergrad rich
    ```
    *   `ruamel.yaml`: For parsing and generating YAML configurations. It follows YAML 1.2, like `clang-format`, so values such as `Yes` and `No` stay strings.
    *   `requests`, `beautifulsoup4`, `lxml`: For scraping `clang-format` documentation to get option values.
    *   `matplotlib`: (Optional) For plotting the fitness history during optimization. If not installed, plotting will be disabled.
    *   `nevergrad`: For black-box optimization algorithms.
    *   `rich`: For the progress bar.

Then run the scripts with `python3 <script>` instead of `uv run <script>`.

## Usage ⚙️
### Recommended Workflow
1.  **Commit** the code to analyze. The tool works on clones of the repository, which contain the committed state of the checked-out branch, not uncommitted changes.
2.  **Choose the `clang-format`** your project uses, e.g. `clang-format-20`.
3.  **Generate the option values** for its version (see [Step 1](#step-1-generate-clang-format-option-values-)).
4.  **Write the forced options**: at least the ones in [Step 2](#step-2-define-forced-options-), plus the style decisions you do not want the tool to change.
5.  **Run the optimizer** from your `.clang-format`, leaving out third-party and generated code:

    ```sh
    uv run main.py /path/to/project \
        --clang-format clang-format-20 \
        --option-values-json clang-format-20-values.json \
        --forced-options-yaml forced.yml \
        --start-config-file /path/to/project/.clang-format \
        --update-start-config \
        --exclude thirdparty \
        --iterations 100 --population-size 32 --islands 8 --jobs 8 \
        --output optimized.clang-format
    ```

6.  **Check the result** by formatting the project with it and reviewing the diff. A fitness that does not go below the start value means that no single option change helps: the remaining changes are usually code that was never formatted, or formatted with another `clang-format` version.

### Step 1: Generate Clang-Format Option Values 📝
The optimizer tests, for each option, the values listed in an option values JSON file. `get_option_values.py` scrapes them from the `clang-format` style options documentation. Pass the release of your `clang-format` (see `clang-format --version`) or its major version:

```sh
uv run get_option_values.py --llvm-version 20.1.8 > clang-format-20-values.json
```

releases.llvm.org has the documentation of the first release of each major version only, so that one is used (e.g. 20.1.0 for 20.1.8); patch releases do not change the options. Without `--llvm-version` the script reads the documentation of the development version. `data/clang-format-values.json` was generated that way: it lists options and values that a released `clang-format` may not know (e.g. `BinPackLongBracedList`, `EnumTrailingComma` are not in `clang-format` 20).

The JSON file can be edited: remove an option to leave it out of the optimization, or add values to it. Integer options such as `ColumnLimit` and the `Penalty*` options have no values in the documentation, so they keep their start values unless you list candidates, e.g.:

```json
{"name": "ColumnLimit", "type": "Unsigned", "possible_values": ["80", "90", "100", "120"]}
```

Boolean options are always tested with `true` and `false`, and the current value of an option is always tested too, even when the list does not have it.

### Step 2: Define Forced Options 🔒
Forced options keep the given value during the whole optimization. Always force:

```yml
DisableFormat: false      # 'true' would trivially change nothing
QualifierAlignment: Leave # 'Custom' needs a QualifierOrder list
```

and add the options you have decided on, e.g. `ColumnLimit` or `IndentWidth`. `data/forced.yml` is an example of such a file with `IndentWidth: 4`, `ColumnLimit: 120` and other choices of its author: do not use it as is for another project, or the result will follow its style, not yours.

`Language` is removed from the configuration unless it is forced: `--dump-config` writes `Language: Cpp`, which `clang-format` refuses for the Objective-C files (`*.m`, `*.mm`) that are formatted too, and without it the result applies to all languages.

### Step 3: Run the Optimizer 🚀
```sh
uv run main.py <repo_path> [OPTIONS]
```

`<repo_path>` is the git repository to analyze. The tool formats its tracked `*.c`, `*.cc`, `*.cpp`, `*.cxx`, `*.h`, `*.hh`, `*.hpp`, `*.hxx`, `*.m` and `*.mm` files, except the excluded ones.

**Input:**
*   `--clang-format <executable>`: The `clang-format` to optimize the configuration for, as a name in `PATH` or a path, e.g. `clang-format-20` (default: `clang-format`). It is checked, and its version printed, before the run starts.
*   `--start-config-file <file_path>`: An existing `.clang-format` to start from. The file is expanded with `clang-format --style=file:<file_path> --dump-config`, so every option is optimized, starting from the file's values (and those of its `BasedOnStyle`). Without it, the tool starts from `clang-format --dump-config` run in the current directory: the style of a `.clang-format` found there or in a parent directory, else the LLVM style. To keep an option of the file unchanged, force it.
*   `--option-values-json <file_path>`: The option values JSON file (see Step 1).
*   `--forced-options-yaml <file_path>`: The forced options YAML file (see Step 2).
*   `--exclude <pathspec>`: Git pathspec of files that are neither formatted nor counted, e.g. `thirdparty` or `'*.pb.h'`. Can be given several times. Use it for third-party and generated code: it does not follow the project's style, and large files can make `clang-format` exceed its timeout of 120 seconds per evaluation.

**Search:**
*   `--optimizer {genetic|nevergrad}`: `genetic` (default) uses a genetic algorithm with an island model; `nevergrad` uses Nevergrad's black-box optimizers.
*   `--iterations <int>`: **[Genetic Algorithm]** Number of generations (default: `100`).
*   `--population-size <int>`: **[Genetic Algorithm]** Total number of individuals across all islands (default: `4`). Each island has at least 5 individuals; the total is raised to match.
*   `--islands <int>`: **[Genetic Algorithm]** Number of independent populations (default: `1`). Every 15 generations, each island sends its best individual to another one.
*   `--ng-budget <int>`: **[Nevergrad]** Total number of evaluations (default: `1000`).
*   `--ng-optimizer <str>`: **[Nevergrad]** Name of the Nevergrad optimizer (default: `OnePlusOne`; e.g. `CMA`, `DE`, `PSO`).

**Evaluation:**
*   `-j`, `--jobs <int>`: Number of parallel evaluations (default: `1`), each in its own temporary clone of the repository. For Nevergrad, this is also its `num_workers`.
*   `--file-sample-percentage <float>`: Percentage of files (0.0-100.0) to evaluate (default: `100.0`). The sample is the same in every evaluation. Lower values are faster but less accurate.

**Output:**
*   `--output <file_path>`: File to write the configuration to (default: `stdout`).
*   `--update-start-config`: Write the result as the `--start-config-file` with only the options that changed, instead of every option of `--dump-config` (see below). Needs `--start-config-file`.
*   `-v`, `--verbose`: Print every evaluation, mutation and per-island result, and every configuration that `clang-format` rejects. By default only the setup, new best results, timeouts, errors and the summary are printed.
*   `-d`, `--debug`: Also print the commands being executed and their output. Implies `--verbose`.
*   `--plot-fitness`: Plot the best fitness over time with `matplotlib`.

### Output
By default the result is every option of the chosen `clang-format` (about 300 lines for `clang-format` 20), without `Language`.

With `--update-start-config`, the result is your start file with only the options that changed:
*   A value that the file sets is replaced in place, keeping the comment after it.
*   An option that the file does not set is added at the end of its parent block (`BraceWrapping`, `KeepEmptyLines`, ...), or of the file.
*   A scalar shorthand such as `AlignConsecutiveAssignments: None` becomes a block of all its sub-options when one of them changes.
*   Everything else (comments, key order, quoting, alignment) stays as it is; when nothing changed, the file is written unchanged.

The result is checked with `clang-format --dump-config` against the full configuration. When an option cannot be written (a flow-style `{...}` parent, a file with several `---` sections) or `clang-format` reads the file differently, the full configuration is written with a warning.

### Progress
On a terminal, a progress bar shows the generations (genetic algorithm) or evaluations (Nevergrad) done, the number and rate of evaluations, the best fitness, the elapsed and the estimated remaining time; new best results are printed above it:

```
Generations ━━━━━━━━━━━━━━━━━━━━━━━━━━╸━━━━━━━━━━━━━ 2/3 evals 63 (2.3/s) best 88 0:00:27 eta 0:00:08
```

When the output is not a terminal, or with `--verbose`, a status line is printed every 30 seconds and at the end:

```
[status] Generations 2/5 (40%) | evals 118 (3.9/s) | best 88 | elapsed 00:30, remaining ~00:45
```

## How It Works 🔬
*   **Fitness**: the configuration is written to a temporary file, `clang-format -i` formats the files of a repository clone, and `git diff --shortstat` counts the inserted and deleted lines; the clone is then restored. A configuration that `clang-format` rejects (e.g. a value it does not know), crashes on, or that exceeds the timeout gets an infinite fitness.
*   **Genetic algorithm**: all individuals start as the base configuration (the start file or the defaults, with the forced options applied). In each generation, every island keeps its best individual and creates new ones by uniform crossover of two random parents, then mutates one random option of each child: every value of that option is tested, and the best one is kept. The islands evolve in parallel.
*   **Nevergrad**: the boolean options and the options with values are the search space; each evaluation is one configuration proposed by the optimizer.

## Limitations
*   Only committed files of the checked-out branch are analyzed.
*   The result is specific to the `clang-format` version used for the optimization.
*   Integer options without values in the option values JSON are not optimized (see Step 1).
*   A single option change is tested at a time: a style that needs several options changed together may not be found.
*   `--update-start-config` supports one YAML document with block-style maps and options nested at most two levels deep.

## Examples
### Genetic Algorithm, From an Existing Config
Optimize the configuration of `/home/user/my_project` for `clang-format` 20, starting from its `.clang-format` and updating it, with 4 islands of 8 individuals, 50 generations, 4 parallel jobs, and a 25% sample of the files:

```sh
uv run main.py /home/user/my_project \
    --clang-format clang-format-20 \
    --option-values-json clang-format-20-values.json \
    --forced-options-yaml forced.yml \
    --start-config-file /home/user/my_project/.clang-format \
    --update-start-config \
    --exclude thirdparty \
    --iterations 50 \
    --population-size 32 \
    --islands 4 \
    --jobs 4 \
    --file-sample-percentage 25.0 \
    --output optimized.clang-format
```

### Genetic Algorithm, From the Defaults
Without a start file, the tool starts from `clang-format --dump-config` in the current directory (the LLVM style when no `.clang-format` is found there or above):

```sh
uv run main.py /home/user/my_project \
    --clang-format clang-format-20 \
    --option-values-json clang-format-20-values.json \
    --forced-options-yaml forced.yml \
    --iterations 50 \
    --population-size 32 \
    --islands 4 \
    --jobs 4 \
    --plot-fitness \
    --output optimized.clang-format
```

### Nevergrad
Optimize with the Nevergrad optimizer `CMA`, a budget of 2000 evaluations and 8 parallel jobs:

```sh
uv run main.py /home/user/my_project \
    --optimizer nevergrad \
    --ng-optimizer CMA \
    --ng-budget 2000 \
    --clang-format clang-format-20 \
    --option-values-json clang-format-20-values.json \
    --forced-options-yaml forced.yml \
    --start-config-file /home/user/my_project/.clang-format \
    --jobs 8 \
    --file-sample-percentage 50.0 \
    --output optimized.clang-format
```

## Testing 🧪
`test.py` is a manual smoke script (`uv run test.py`): it creates a small git repository and runs the optimizer's value test for `DerivePointerAlignment` with `data/clang-format-values.json` and `data/forced.yml`. That example forces `DerivePointerAlignment`, so the script skips it and only checks that the modules load and run.

## Contributing 👋
Contributions are welcome! Please feel free to open issues or pull requests.

## License 📄
This project is licensed under the terms specified in the `LICENSE` file.
