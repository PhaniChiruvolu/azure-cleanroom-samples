import json
import logging
from datasets import load_dataset
from transformers import (
    Trainer,
    TrainingArguments,
    DistilBertForSequenceClassification,
    DistilBertTokenizerFast,
    DataCollatorWithPadding,
)
from optimum.onnxruntime import ORTModel

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, BaseModel

# Create a logger from the global logger provider.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("training")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True)
    training_model_path: str = Field(alias="model-path")
    dataset_path: str = Field(alias="dataset-path")
    training_arguments_path: str = Field(alias="training-arguments-path")
    output_path: str = Field(alias="output-path")


class ModelTrainingArguments(BaseModel):
    num_epochs: int = Field(default=3)
    warmup_steps: int = Field(default=500)
    weight_decay: float = Field(default=0.01)
    per_device_train_batch_size: int = Field(default=8)
    gradient_accumulation_steps: int = Field(default=4)
    learning_rate: float = Field(default=2e-5)
    evaluation_strategy: str = Field(default="epoch")
    fp16: bool = Field(default=False)
    dataloader_num_workers: int = Field(default=4)
    use_cpu: bool = Field(default=False)


def runTraining(settings: AppSettings):

    model = DistilBertForSequenceClassification.from_pretrained(
        settings.training_model_path
    )

    logger.info(
        f"Loading DistilBert model from {settings.training_model_path} for fine-tuning"
    )
    tokenizer = DistilBertTokenizerFast.from_pretrained(settings.training_model_path)

    logger.info(f"Loading datasets from {settings.dataset_path} for fine-tuning")

    # Load the dataset
    dataset = load_dataset(settings.dataset_path)

    def tokenize_function(examples):
        return tokenizer(examples["text"], padding="max_length", truncation=True)

    tokenized_datasets = dataset.map(tokenize_function, batched=True)

    logger.info(
        f"Loading training arguments from {settings.training_arguments_path} for fine-tuning"
    )

    # Load the training arguments
    with open(settings.training_arguments_path, "r") as f:
        training_arguments = json.loads(f.read())
    model_training_args = ModelTrainingArguments(**training_arguments)

    # Train
    training_args = TrainingArguments(
        output_dir=settings.output_path,
        num_train_epochs=model_training_args.num_epochs,
        warmup_steps=model_training_args.warmup_steps,
        weight_decay=model_training_args.weight_decay,
        per_device_train_batch_size=model_training_args.per_device_train_batch_size,
        gradient_accumulation_steps=model_training_args.gradient_accumulation_steps,
        learning_rate=model_training_args.learning_rate,
        eval_strategy=model_training_args.evaluation_strategy,
        fp16=model_training_args.fp16,
        logging_dir=settings.output_path,
        dataloader_num_workers=model_training_args.dataloader_num_workers,
        use_cpu=model_training_args.use_cpu,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["validation"],
    )

    trainer.train()

    logger.info(f"Dumping trained model to {settings.output_path}/trained_model")

    # Dump the output model into output_path
    trained_model_path = settings.output_path + "/trained_model"
    model.save_pretrained(trained_model_path)
    tokenizer.save_pretrained(trained_model_path)

    logger.info(
        f"Dumping trained ONNX model to {settings.output_path}/trained_model_onnx"
    )

    # Dump the onnx model that is to be used for inferencing
    model = ORTModel.from_pretrained(trained_model_path, export=True)
    model.save_pretrained(trained_model_path + "_onnx")
    tokenizer.save_pretrained(trained_model_path + "_onnx")


def main(settings: AppSettings):
    runTraining(settings)


settings = AppSettings()
if __name__ == "__main__":
    main(settings)
