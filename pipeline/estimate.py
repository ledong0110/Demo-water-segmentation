import numpy as np
import cv2
import math
from numpy.linalg import norm
import os

from pathlib import Path
from torch.utils import data
# import albumentations as album
from PIL import Image
import torchvision.transforms as tf
from utility import utils


#########################################################################
# Với mỗi một camera , dùng hàm initialize_save_point để khởi tạo các điểm ( khi gọi sẽ hiện lên ảnh rồi chọn điểm thủ công)
# Sau đó gọi hàm calculate_water_depth để tính toán độ sâu của nước
# Chỗ chọn ảnh thủ công có thể cải thiện thêm, chẳng hạn như vẽ đường khi chọn dc 2 điểm, hiện tọa độ theo con trỏ chuột
#
# Có thể điều chỉnh để chọn nhiều vật hơn, hiện tại đang set chỉ để chọn 2 vật ( lề đường với biển báo)
# 

# Còn về ý tưởng thuật toán thì đã nói trong mess, hạn chế là nếu ảnh mờ và góc camera quá cao thì sẽ không chính xác cho lắm
########################################################################

# Fucntion to transform 3D mask to 2D mask
def transform_mask_3D_to_2D(img_mask_path,img_original,list_1,list_2):
    water_mask = cv2.imread(img_mask_path)
    image = cv2.imread(img_original)
    image_size = image.shape
    water_mask = cv2.resize(water_mask, (image_size[1],image_size[0]))
    
    basename = str(Path(os.path.basename(img_original)).stem)
    over_savepth = os.path.join(os.getenv('STORAGE'),'depth_estimation',basename + '.png')
    overlay_path = os.path.join(os.getenv('STORAGE'),'overlay',basename + '.png')
    overlay_image = cv2.imread(overlay_path)
    
    image = overlay_image
    
    
    for i in range(0,int(len(list_1)/2)+2,2):  # vẽ line
        cv2.line(image, list_1[i], list_1[i+2], (0, 0, 255), 6)
        cv2.line(image, list_1[i+1], list_1[i+3], (0, 0, 255), 6)
        
    for i in range(0,int(len(list_2)/2)+2,2):  # vẽ line
        cv2.line(image, list_2[i], list_2[i+2], (0, 0, 255), 6)
        cv2.line(image, list_2[i+1], list_2[i+3], (0, 0, 255), 6)
        
    cv2.imwrite(over_savepth, image)
        
    check = np.zeros(water_mask.shape[0:2])
    for i in range(water_mask.shape[0]):
        for j in range(water_mask.shape[1]):
            if water_mask[i,j,0] >50 :
                check[i,j] =255 
        
    water_mask = check
    return water_mask



#####################################################
#####################################################


# Function to calculate the position when the object touch the water
def pos_when_touch_water(point,point_2,water_mask,vector,height):
    for step in range(int(height)):
        p = (point - vector * step).astype(int) # điểm trên cùng + vector hướng * bước
        if water_mask[p[1], p[0]] == 255: # nếu điểm trên cùng + vector hướng * bước nằm trong nước thì
            water_touch_pos = p # đáy của nước = điểm trên cùng + vector hướng * bước ngay lúc nó ngang mặt 
            return water_touch_pos  
    print("chưa chạm nước")
    return point_2  # return point_2 nếu chưa chạm nước


# Function to calculate the submerged length
def cal_distance_water(point_top, point_below,point_touch_water,object_real_size):
    dis_real = cal_distances(point_top , point_below)
    dis_touch = cal_distances(point_top , point_touch_water)
    dis = object_real_size*(1-(dis_touch/dis_real))
    print("dis_real",(dis_touch/dis_real))
    return dis
    
# Function to calculate the distance between 2 points
def cal_distances(point_1,point_2):
    dis = math.sqrt((point_1[0]-point_2[0])**2 + (point_1[1]-point_2[1])**2)
    return dis

# Function to calculate the normal vector
def cal_norm_vector(point_1,point_2):
    vector = np.array(point_1) - np.array(point_2)
    vector = vector/np.linalg.norm(vector)
    return vector

def predict_level(length):
    if length <=10:
        return 0
    elif length <=30:
        return 1
    elif length <=50:
        return 2
    else:
        return 3


# Function to calculate the average submerged length
def calculate_water_depth(mask_path,image_path,object_real_size, object_real_size_2, point, point_2):
    #input: 
    #       mask_path: path of mask
    #       object_real_size: real size of object 1
    #       object_real_size_2: real size of object 2
    #       point: list of points of object 1
    #       point_2: list of points of object 2
    water_mask = transform_mask_3D_to_2D(mask_path,image_path,point,point_2) # mask 3D -> 2D

    average_submerged_length = 0
    average_submerged_length_2=0
    
    sign = 0
    for i in range(0,len(point),2):
        point_touch_water = pos_when_touch_water(point[i],point[i+1],water_mask,cal_norm_vector(point[i],point[i+1]),cal_distances(point[i],point[i+1])) # điểm chìm
        
        average_submerged_length += cal_distance_water(point[i],point[i+1],point_touch_water,object_real_size) # tính độ sâu chìm của các đối tượng      
        if point_touch_water[0] == point[i][0] and point_touch_water[1] == point[i][1]:
            sign = 1
       
    average_submerged_length = average_submerged_length/int((len(point)/2))
    
    print("length_1",average_submerged_length)
    
    # khi điểm trên cùng của bất kì điểm nào nằm trong nước thì kích hoạt hàm 2, trả về 
    # độ chìm trung bình của các điểm case 2 rồi cộng vào 
    if sign == 1:
        
        for i in range(0,len(point_2),2):
            point_touch_water = pos_when_touch_water(point_2[i],point_2[i+1],water_mask,cal_norm_vector(point_2[i],point_2[i+1]),cal_distances(point_2[i],point_2[i+1])) # điểm chìm
            print("point_touch_water_1111",point_touch_water)
            average_submerged_length_2 += cal_distance_water(point_2[i],point_2[i+1],point_touch_water,object_real_size_2) # tính độ sâu chìm của các đối tượng
        
        
        average_submerged_length_2 = average_submerged_length_2/int((len(point_2)/2))
        print("length_2",average_submerged_length_2)
        
    level = predict_level(average_submerged_length + average_submerged_length_2 )
    
    #return average_submerged_length + average_submerged_length_2  # trung bình độ sâu chìm của các đối tượng
    return level



# if __name__ == "__main__":
#     object_real_size_1 = 100 # real size of object
#     object_real_size_2 = 200 # real size of object 2

#     save_point = get_click_point('real.jpg')
#     save_point_2 = get_click_point_2('real.jpg')
    
#     a  = calculate_water_depth('mask.png',object_real_size_1, object_real_size_2, save_point, save_point_2)
#     print(a)
    
