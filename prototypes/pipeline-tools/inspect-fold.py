from PIL import Image
import io,base64
im=Image.open('../pipeline-wireframes/qa/proposals-1280.png')
im=im.crop((0,0,1280,720))
b=io.BytesIO();im.save(b,format='JPEG',quality=80)
print(base64.b64encode(b.getvalue()).decode())
