import numpy as np
import glob
from PIL import Image
import matplotlib.pyplot as plt

def swatch_avg(img):
    return np.array([[np.round(np.average(img, axis = (0,1)))]], dtype=np.int16)

def unique_pixels(img):
    flattened_img = np.vstack(img)
    print(f"total pixels: {len(flattened_img)}")
    return np.unique(flattened_img, axis=0)


if __name__ == "__main__":
    imarray = (np.random.rand(100,100,3) * 255).astype('uint8')
    test_img = Image.fromarray(imarray).convert('RGBA')

    print(len(unique_pixels(imarray)))
    imgplot = plt.imshow(test_img)
    plt.show()

    imgplot = plt.imshow(swatch_avg(test_img))
    plt.show()

    swatch_dir = '../data/swatches/'
    for swatch in glob.glob(f"{swatch_dir}*"):
        print(swatch)
        img = np.asarray(Image.open(swatch))
        imgplot = plt.imshow(img)
        plt.show()
        print(img.shape)
        print(len(unique_pixels(img)))
        imgplot = plt.imshow(swatch_avg(img))
        plt.show()