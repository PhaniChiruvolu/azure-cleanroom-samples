import logging
import requests
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from datasets import load_dataset


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True)
    dataset_path: str = Field(alias="dataset-path")
    inference_url: str = Field(alias="inference-url")
    proxy_url: str = Field(alias="proxy-url")


# Create a logger from the global logger provider.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inferencing-client")

app_settings = AppSettings()


def data(dataset):
    for key in dataset.shuffle():
        yield key["text"], key["label"]


def do_infer():
    dataset = load_dataset(app_settings.dataset_path, split="test")
    success_count = 0
    for key in data(dataset):
        inferred_result = do_request(key[0], app_settings.inference_url)
        expected_result = key[1]
        if inferred_result == expected_result:
            success_count += 1
        logger.info(
            f"Inference Result: {inferred_result}. Expected result: {expected_result}"
        )

    success_percentage = (success_count * 100.0) / dataset.num_rows
    logger.info(f"Total rows in dataset: {dataset.num_rows}")
    logger.info(f"Total number of succesful predictions: {success_count}")
    logger.info(f"Success percentage: {success_percentage}")


def do_request(text: str, url: str):
    payload = {"data": text}
    proxies = {"http": app_settings.proxy_url}
    resp = requests.post(url=url, proxies=proxies, json=payload)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    do_infer()
