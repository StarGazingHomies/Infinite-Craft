import math

import llama_cpp
from huggingface_hub import hf_hub_download
from llama_cpp import Llama


WORD_TOKEN_LIMIT = 20
WORD_COMBINE_CHAR_LIMIT = 30
DEFAULT_STARTING_ITEMS = ("Water", "Fire", "Wind", "Earth")


def pair_to_int(i: int, j: int) -> int:
    if j < i:
        i, j = j, i
    return i + (j * (j + 1)) // 2


def int_to_pair(n: int) -> tuple[int, int]:
    if n < 0:
        return -1, -1
    j = math.floor(((8 * n + 1) ** 0.5 - 1) / 2)
    i = n - (j * (j + 1)) // 2
    return i, j


def to_start_case(s: str) -> str:
    new_str = ""
    for i in range(len(s)):
        if i == 0 or s[i - 1] == " ":
            new_str += s[i].upper()
        else:
            new_str += s[i].lower()
    return new_str


class Tokenizer:
    model: Llama
    tokenizer: llama_cpp.LlamaTokenizer

    def __init__(self, name: str = "Havmand/minillama", file: str = "minillama.gguf"):
        self.model = Llama(hf_hub_download(name, filename=file))
        self.tokenizer = self.model.tokenizer()

    def tokenize(self, text: str) -> list[int]:
        return self.tokenizer.tokenize(bytes(text, "utf-8"))

    def decode(self, tokens: list[int]) -> str:
        return self.tokenizer.decode(tokens)


if __name__ == "__main__":
    # model_name = "Havmand/minillama"
    # model_file = "minillama.gguf"
    t = Tokenizer()

    # model_name = "TheBloke/CodeLlama-7B-GGUF"
    # model_file = "codellama-7b.Q2_K.gguf"
    # model_path = hf_hub_download(model_name, filename=model_file)

    # Load the model, tokenizer only
    # model = Llama(model_path)
    # tokenizer: llama_cpp.LlamaTokenizer = model.tokenizer()

    prompt = "- J a y -"
    print(f"Prompt: {prompt}")

    # Tokenize the prompt
    tokens = t.tokenize(prompt)
    print(f"{len(tokens) - 1} tokens: {tokens}")

    # Decode the tokens
    for token in tokens:
        if token == 1:
            print(f"Token: {token}, <Start Token>")
        else:
            print(f"Token: {token}, {t.decode([token])}")