# Weights directory

`cats_focus_best.pt` is the deployment model used by `cat_web_app.py`.

The `.gitignore` is configured to keep historical checkpoints and pretrained base models out of GitHub while allowing this one final deployment weight.

If you do not want to publish model weights in the repository, remove `weights/cats_focus_best.pt` before upload and publish it through GitHub Releases or another model hosting location instead.
