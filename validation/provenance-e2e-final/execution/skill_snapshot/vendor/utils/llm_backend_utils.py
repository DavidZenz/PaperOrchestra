# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Modified: replaced provider routing with the separate-agent Codex transport.
"""Codex transport adaptation; original API signatures, original response parsers.

All requested upstream model names are recorded and mapped to independently
executed Codex agents. No direct OpenAI/Gemini API clients are imported.
"""
from google.genai import types
from utils.gemini_utils import (
    call_gemini_with_text_prompt, call_gemini_with_contents,
    call_gemini_with_images, parse_gemini_json_results,
)


def identity_parse(response):
    return response


def get_llm_parser(model_name, return_json=True):
    return parse_gemini_json_results if return_json else identity_parse


def call_llm_with_text_prompt(prompt, model_name, generation_configs=None,
                              check_parsed_response_not_none=True, return_json=True,
                              result_parsing_func=None):
    return call_gemini_with_text_prompt(
        prompt=prompt, model_name=model_name, generation_configs=generation_configs or {},
        check_parsed_response_not_none=check_parsed_response_not_none,
        result_parsing_func=result_parsing_func or get_llm_parser(model_name, return_json))


def call_llm_with_images(prompt, images, model_name, generation_configs=None,
                         check_parsed_response_not_none=True, return_json=True,
                         result_parsing_func=None):
    return call_gemini_with_images(
        prompt=prompt, images=images, model_name=model_name,
        generation_configs=generation_configs or {},
        check_parsed_response_not_none=check_parsed_response_not_none,
        result_parsing_func=result_parsing_func or get_llm_parser(model_name, return_json))


def call_llm_with_pdf(pdf_path, prompt, model_name, system_instruction=None,
                      temperature=0.7, check_parsed_response_not_none=True,
                      return_json=True, result_parsing_func=None):
    contents = [types.Part.from_bytes(data=open(pdf_path, "rb").read(), mime_type="application/pdf"),
                types.Part.from_text(text=prompt)]
    config = {"temperature": temperature}
    if system_instruction is not None:
        config["system_instruction"] = system_instruction
    return call_gemini_with_contents(
        contents=contents, model_name=model_name, generation_configs=config,
        check_parsed_response_not_none=check_parsed_response_not_none,
        result_parsing_func=result_parsing_func or get_llm_parser(model_name, return_json))
