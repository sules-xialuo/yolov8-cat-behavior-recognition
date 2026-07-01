from ultralytics import YOLO


def main():
    model = YOLO("weights/cats_focus_best.pt")
    model.train(
        data="yolo-cats-focus.yaml",
        epochs=15,
        patience=5,
        imgsz=768,
        batch=8,
        device=0,
        workers=0,
        cache=False,
        amp=False,
        pretrained=True,
        optimizer="AdamW",
        seed=0,
        deterministic=True,
        lr0=0.00005,
        lrf=0.01,
        cos_lr=True,
        warmup_epochs=0.0,
        warmup_bias_lr=0.0001,
        weight_decay=0.0005,
        box=7.5,
        cls=0.8,
        dfl=1.5,
        mosaic=0.0,
        mixup=0.0,
        degrees=0.5,
        translate=0.01,
        scale=0.05,
        fliplr=0.5,
        close_mosaic=0,
        freeze=0,
        multi_scale=False,
        save=True,
        save_period=5,
        plots=True,
        name="cats_focus_ear_pupil_round2_finetune",
    )


if __name__ == "__main__":
    main()
