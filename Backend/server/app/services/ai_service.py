import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageOps
from torchvision import models, transforms
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. CẤU HÌNH ĐƯỜNG DẪN MÔ HÌNH & SIÊU THAM SỐ SUY LUẬN
# ==============================================================================
# Tự động tìm file trọng số ở thư mục gốc của project hoặc thông qua biến môi trường
BASE_DIR = Path(__file__).resolve().parent.parent
YOLO_MODEL_PATH = os.environ.get("YOLO_MODEL_PATH", str(BASE_DIR / "model_yolov11_v1.pt"))
CNN_MODEL_PATH = os.environ.get("CNN_MODEL_PATH", str(BASE_DIR / "model_resnet50_v1.pth"))

# Nếu chạy lệnh từ thư mục hiện hành mà đường dẫn tuyệt đối chưa khớp, fallback về tên file tương đối
if not Path(YOLO_MODEL_PATH).exists() and Path("model_yolov11_v1.pt").exists():
    YOLO_MODEL_PATH = "model_yolov11_v1.pt"
if not Path(CNN_MODEL_PATH).exists() and Path("model_resnet50_v1.pth").exists():
    CNN_MODEL_PATH = "model_resnet50_v1.pth"

NUM_CLASSES = 43

# Ngưỡng phát hiện và định tuyến (Smart Conditional Cascade Thresholds)
YOLO_PROPOSAL_CONF = 0.25      # Hạ xuống 0.25 ở bước 1 để không bỏ sót các món khó (Bánh bột lọc, Mít trộn)
YOLO_IOU_THRESHOLD = 0.45      # Ngưỡng NMS của YOLO
FINAL_CONF_THRESHOLD = 0.35    # Ngưỡng hiển thị cuối cùng trả về cho Frontend (>= 35%)
HIGH_CONF_BYPASS_CNN = 0.80    # Nếu YOLO >= 0.80 VÀ không thuộc nhóm dễ nhầm -> Bỏ qua CNN để tăng tốc

# Tham số cắt ảnh cho CNN (Khớp 100% với pipeline tạo Dataset-CNN-43class)
CONTEXT_PADDING = 0.05         # Mở rộng 5% mỗi cạnh Bounding Box để giữ ngữ cảnh bát/đĩa
MIN_CNN_BOX_SIZE = 32          # Khung nhỏ hơn 32x32 px sẽ giữ nguyên kết quả YOLO (tránh vỡ hạt khi phóng lên 224x224)
LABEL_SMOOTHING_FACTOR = 0.90  # Hiệu chuẩn lại xác suất đỉnh của Exp03 (do train với label_smoothing=0.1)

# Danh sách ID các lớp thuộc nhóm:
# (1) 8 đặc sản Đà Nẵng (ID 35 -> 42)
# (2) Các cặp món có giao thoa đặc trưng mạnh (Món cuốn, Cơm gà, Món nước sợi trắng, Món trộn)
DANANG_CLASS_IDS = set(range(35, 43))
CONFUSABLE_CLASS_IDS = {
    0,   # Banh canh
    2,   # Banh cuon
    9,   # Bun bo Hue
    13,  # Bun rieu
    14,  # Cha gio
    15,  # Com tam
    16,  # Goi cuon (dễ nhầm với banh_trang_cuon_thit_heo)
    18,  # Hu tieu
    22,  # Pho
    25,  # Banh beo
    26,  # Cao lau
    27,  # Mi Quang
    29,  # Bun cha ca
    30,  # Com chien ga (dễ nhầm với com_ga_hoi_an)
    32,  # Nom hoa chuoi (dễ nhầm với mit_tron)
} | DANANG_CLASS_IDS

# Bảng mã màu nổi bật gắn cho từng món ăn trên Frontend
COLOR_PALETTE = [
    "#FF3B30",  # 1. Đỏ cam
    "#34C759",  # 2. Xanh lá
    "#007AFF",  # 3. Xanh dương
    "#FF9500",  # 4. Vàng cam
    "#AF52DE",  # 5. Tím
    "#00C7BE",  # 6. Xanh ngọc
    "#FF2D55",  # 7. Hồng đậm
    "#FFCC00",  # 8. Vàng tươi
]


# ==============================================================================
# 2. ĐỊNH NGHĨA KIẾN TRÚC RESNET-50 + CBAM (KHỚP 100% VỚI FILE TRAIN EXP03)
# ==============================================================================
class ChannelAttention(nn.Module):
    def __init__(self, in_planes: int, reduction: int = 16):
        super().__init__()
        mid_planes = max(in_planes // reduction, 16)
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.shared_mlp = nn.Sequential(
            nn.Conv2d(in_planes, mid_planes, kernel_size=1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_planes, in_planes, kernel_size=1, bias=False),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg_out = self.shared_mlp(self.avg_pool(x))
        max_out = self.shared_mlp(self.max_pool(x))
        return x * torch.sigmoid(avg_out + max_out)


class SpatialAttention(nn.Module):
    def __init__(self, kernel_size: int = 7):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(2, 1, kernel_size, padding=kernel_size // 2, bias=False),
            nn.BatchNorm2d(1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg_out = torch.mean(x, dim=1, keepdim=True)
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        spatial = torch.cat([avg_out, max_out], dim=1)
        return x * torch.sigmoid(self.conv(spatial))


class CBAMBlock(nn.Module):
    def __init__(self, in_planes: int, reduction: int = 16, spatial_kernel: int = 7):
        super().__init__()
        self.ca = ChannelAttention(in_planes, reduction=reduction)
        self.sa = SpatialAttention(kernel_size=spatial_kernel)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return 0.5 * self.sa(self.ca(x)) + 0.5 * x


class ResNet50_CBAM(nn.Module):
    def __init__(self, num_classes: int = NUM_CLASSES):
        super().__init__()
        # weights=None khi khởi tạo ở Backend để không phải tải lại file 98MB của ImageNet từ internet
        base = models.resnet50(weights=None)
        self.conv1 = base.conv1
        self.bn1 = base.bn1
        self.relu = base.relu
        self.maxpool = base.maxpool
        self.layer1 = base.layer1
        self.layer2 = base.layer2
        self.layer3 = base.layer3
        self.cbam3 = CBAMBlock(1024)
        self.layer4 = base.layer4
        self.cbam4 = CBAMBlock(2048)
        self.avgpool = base.avgpool
        self.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(2048, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.maxpool(self.relu(self.bn1(self.conv1(x))))
        x = self.layer2(self.layer1(x))
        x = self.cbam4(self.layer4(self.cbam3(self.layer3(x))))
        return self.classifier(torch.flatten(self.avgpool(x), 1))


# ==============================================================================
# 3. KHỞI TẠO THIẾT BỊ & NẠP MÔ HÌNH MỘT LẦN KHI START SERVER
# ==============================================================================
def get_optimal_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")  # Tối ưu cho Apple Silicon (MacBook M1/M2/M3)
    return torch.device("cpu")


DEVICE = get_optimal_device()
logger.info(f"🚀 AI Service đang chạy trên thiết bị: {DEVICE}")

# Phép biến đổi ảnh chuẩn cho CNN Evaluation (Resize 256 -> CenterCrop 224 -> Normalize ImageNet)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

cnn_eval_transform = transforms.Compose([
    transforms.Resize((256, 256)),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])

# 3.1. Nạp mô hình YOLO11
if not Path(YOLO_MODEL_PATH).exists():
    raise FileNotFoundError(f"❌ Không tìm thấy trọng số YOLO tại: {YOLO_MODEL_PATH}")

yolo_model = YOLO(YOLO_MODEL_PATH)
logger.info(f"✅ Đã nạp thành công mô hình YOLO: {YOLO_MODEL_PATH}")

# 3.2. Nạp mô hình CNN (ResNet-50 + CBAM Exp03)
cnn_model: Optional[nn.Module] = None

def load_cnn_model(weight_path: str) -> Optional[nn.Module]:
    path_obj = Path(weight_path)
    if not path_obj.exists():
        logger.warning(
            f"⚠️ Không tìm thấy file trọng số CNN tại '{weight_path}'. "
            f"Hệ thống sẽ tự động chạy ở chế độ dự phòng (YOLO-Only)."
        )
        return None

    try:
        ckpt = torch.load(path_obj, map_location=DEVICE, weights_only=False)
        state_dict = ckpt["model_state_dict"] if isinstance(ckpt, dict) and "model_state_dict" in ckpt else ckpt

        # Tự động kiểm tra xem file .pth là bản ResNet50_CBAM (Exp02/Exp03) hay ResNet50 thuần (Exp01)
        is_cbam = any("cbam" in k or "classifier" in k for k in state_dict.keys())
        if is_cbam:
            net = ResNet50_CBAM(num_classes=NUM_CLASSES)
            arch_name = "ResNet50_CBAM (Exp03)"
        else:
            net = models.resnet50(weights=None)
            net.fc = nn.Linear(net.fc.in_features, NUM_CLASSES)
            arch_name = "ResNet50_Baseline (Exp01)"

        net.load_state_dict(state_dict, strict=True)
        net.to(DEVICE)
        net.eval()
        logger.info(f"✅ Đã nạp thành công mô hình CNN [{arch_name}] từ: {weight_path}")
        return net
    except Exception as exc:
        logger.error(f"❌ Lỗi khi nạp mô hình CNN ({weight_path}): {exc}. Chuyển sang chế độ YOLO-Only.")
        return None


cnn_model = load_cnn_model(CNN_MODEL_PATH)


# ==============================================================================
# 4. CÁC HÀM HỖ TRỢ CẮT ẢNH, ĐỊNH TUYẾN & HỢP NHẤT XÁC SUẤT (LATE FUSION)
# ==============================================================================
def should_trigger_cnn(cls_id: int, conf_yolo: float, box_w: float, box_h: float) -> bool:
    """
    Bộ định tuyến thông minh (Smart Conditional Router):
    Quyết định xem một khung hình của YOLO có cần đưa qua CNN thẩm định lại hay không.
    """
    if cnn_model is None:
        return False

    # 1. Nếu vùng cắt quá nhỏ (< 32x32 pixel), phóng lên 224x224 sẽ bị nhòe -> Giữ nguyên YOLO
    if box_w < MIN_CNN_BOX_SIZE or box_h < MIN_CNN_BOX_SIZE:
        return False

    # 2. Nếu độ tự tin của YOLO chưa đạt ngưỡng chắc chắn (< 0.80) -> Kích hoạt CNN
    if conf_yolo < HIGH_CONF_BYPASS_CNN:
        return True

    # 3. Ngay cả khi YOLO tự tin >= 0.80, nếu lớp dự đoán nằm trong nhóm Đặc sản Đà Nẵng
    #    hoặc nhóm món dễ nhầm lẫn (Gỏi cuốn vs Bánh tráng cuốn thịt heo...) -> Bắt buộc CNN kiểm tra chéo
    if cls_id in CONFUSABLE_CLASS_IDS:
        return True

    return False


def crop_with_context_padding(
    image: Image.Image, xyxy: List[float], img_w: int, img_h: int
) -> Image.Image:
    """Cắt vùng món ăn kèm mở rộng biên 5% giống hệt quá trình tạo Dataset huấn luyện CNN."""
    x1, y1, x2, y2 = xyxy
    bw = x2 - x1
    bh = y2 - y1
    pad_w = bw * CONTEXT_PADDING
    pad_h = bh * CONTEXT_PADDING

    cx1 = max(0, int(round(x1 - pad_w)))
    cy1 = max(0, int(round(y1 - pad_h)))
    cx2 = min(img_w, int(round(x2 + pad_w)))
    cy2 = min(img_h, int(round(y2 + pad_h)))
    return image.crop((cx1, cy1, cx2, cy2))


def fuse_yolo_and_cnn_decision(
        yolo_cls_id: int,
        yolo_conf: float,
        cnn_probs: torch.Tensor,
) -> Tuple[int, float, str]:
    """
    Hợp nhất quyết định giữa YOLO11 và ResNet50_CBAM với điều kiện Semantic Veto nghiêm ngặt.
    """
    cnn_cls_id = int(torch.argmax(cnn_probs).item())
    raw_cnn_conf = float(cnn_probs[cnn_cls_id].item())

    # Hiệu chuẩn xác suất của Exp03 (Label Smoothing)
    calibrated_cnn_conf = min(0.995, raw_cnn_conf / LABEL_SMOOTHING_FACTOR)

    # TRƯỜNG HỢP 1: Cả 2 cùng đồng thuận
    if cnn_cls_id == yolo_cls_id:
        fused_conf = (0.45 * yolo_conf) + (0.55 * calibrated_cnn_conf)
        final_conf = max(yolo_conf, fused_conf)
        return yolo_cls_id, min(0.995, final_conf), "YOLO11+ResNet50_CBAM(Agreed)"

    # TRƯỜNG HỢP 2: Bất đồng quan điểm (Disagreement)
    cnn_prob_for_yolo_cls = float(cnn_probs[yolo_cls_id].item()) / LABEL_SMOOTHING_FACTOR

    # Kịch bản A: Cả YOLO và CNN đều đang tranh luận trong nội bộ nhóm "dễ nhầm lẫn"
    both_in_confusable = (yolo_cls_id in CONFUSABLE_CLASS_IDS) and (cnn_cls_id in CONFUSABLE_CLASS_IDS)

    # Cho phép CNN sửa nhãn mượt mà nếu cùng nằm trong nhóm dễ nhầm
    valid_internal_refinement = both_in_confusable and (calibrated_cnn_conf >= 0.45) and (
                calibrated_cnn_conf >= yolo_conf * 0.70)

    # Kịch bản B: CNN đòi đổi sang một món KHÔNG liên quan (Cross-domain Veto)
    # Ví dụ: YOLO đoán Cơm gà Hội An, CNN đòi đổi thành Bánh xèo
    # Ép điều kiện cực gắt: CNN phải > 0.85 VÀ YOLO phải rất yếu (< 0.55)
    cross_domain_veto = (not both_in_confusable) and (calibrated_cnn_conf >= 0.85) and (yolo_conf < 0.55)

    # Thực thi lật kèo nếu thỏa mãn 1 trong 2 kịch bản an toàn
    if valid_internal_refinement or cross_domain_veto:
        final_conf = (0.65 * calibrated_cnn_conf) + (0.35 * yolo_conf)
        return cnn_cls_id, min(0.995, final_conf), "ResNet50_CBAM(Refined)"

    # TRƯỜNG HỢP 3: CNN khác biệt nhưng không đủ bằng chứng vững chắc -> Từ chối lật kèo, tin YOLO
    # Điều chỉnh lại độ tự tin của YOLO bị giảm nhẹ do CNN không đồng tình
    adjusted_yolo_conf = (0.80 * yolo_conf) + (0.20 * min(1.0, cnn_prob_for_yolo_cls))
    return yolo_cls_id, adjusted_yolo_conf, "YOLO11(Retained)"


# ==============================================================================
# 5. HÀM XỬ LÝ CHÍNH ĐƯỢC GỌI TỪ API ENDPOINT `/predict`
# ==============================================================================
def process_image_and_predict(file_bytes: bytes) -> dict:
    """
    Thực thi pipeline nhận diện món ăn 2 giai đoạn (YOLO11 + ResNet50_CBAM)
    và trả về JSON đúng chuẩn cấu trúc của Frontend.
    """
    t_start = time.perf_counter()

    # 1. Đọc ảnh & tự động xoay đúng chiều EXIF
    try:
        original_image = Image.open(io.BytesIO(file_bytes))
        original_image = ImageOps.exif_transpose(original_image).convert("RGB")
        img_width, img_height = original_image.size
    except Exception:
        raise ValueError("Không thể đọc được file ảnh. Vui lòng thử lại.")

    # 2. GIAI ĐOẠN 1: Chạy YOLO11 với ngưỡng đề xuất (Proposal Threshold = 0.25)
    results = yolo_model.predict(
        source=original_image,
        conf=YOLO_PROPOSAL_CONF,
        iou=YOLO_IOU_THRESHOLD,
        verbose=False,
    )
    res = results[0]

    # Thu thập danh sách các Bounding Box từ YOLO
    proposals = []
    crops_for_cnn = []
    proposal_indices_for_cnn = []

    for box in res.boxes:
        conf_yolo = float(box.conf[0])
        cls_yolo = int(box.cls[0])
        xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]

        x1, y1, x2, y2 = xyxy
        box_w = max(0.0, x2 - x1)
        box_h = max(0.0, y2 - y1)

        item = {
            "yolo_cls_id": cls_yolo,
            "yolo_conf": conf_yolo,
            "final_cls_id": cls_yolo,
            "final_conf_raw": conf_yolo,
            "xyxy": xyxy,
            "source_model": "YOLO11(FastPath)",
        }
        prop_idx = len(proposals)
        proposals.append(item)

        # Kiểm tra điều kiện định tuyến sang CNN
        if should_trigger_cnn(cls_yolo, conf_yolo, box_w, box_h):
            cropped_img = crop_with_context_padding(original_image, xyxy, img_width, img_height)
            crops_for_cnn.append(cnn_eval_transform(cropped_img))
            proposal_indices_for_cnn.append(prop_idx)

    # 3. GIAI ĐOẠN 2: Chạy Batched CNN Inference (chỉ chạy 1 lần cho tất cả các box cần thẩm định)
    if crops_for_cnn and cnn_model is not None:
        batch_tensor = torch.stack(crops_for_cnn, dim=0).to(DEVICE)
        with torch.inference_mode():
            logits = cnn_model(batch_tensor)
            probs_batch = F.softmax(logits, dim=1).cpu()

        for batch_i, prop_idx in enumerate(proposal_indices_for_cnn):
            prop = proposals[prop_idx]
            final_cid, final_conf, src_tag = fuse_yolo_and_cnn_decision(
                yolo_cls_id=prop["yolo_cls_id"],
                yolo_conf=prop["yolo_conf"],
                cnn_probs=probs_batch[batch_i],
            )
            prop["final_cls_id"] = final_cid
            prop["final_conf_raw"] = final_conf
            prop["source_model"] = src_tag

    # 4. GIAI ĐOẠN 3: Lọc theo ngưỡng hiển thị cuối cùng (>= 0.35) & Lọc trùng món (Deduplication)
    best_per_class: Dict[str, dict] = {}

    for prop in proposals:
        conf_final = prop["final_conf_raw"]
        if conf_final < FINAL_CONF_THRESHOLD:
            continue

        cls_id = prop["final_cls_id"]
        cls_name = yolo_model.names[cls_id]

        if cls_name not in best_per_class or conf_final > best_per_class[cls_name]["conf_raw"]:
            best_per_class[cls_name] = {
                "class_id": cls_id,
                "class_name": cls_name,
                "conf_raw": conf_final,
                "confidence": round(conf_final * 100, 2),
                "xyxy": prop["xyxy"],
                "source_model": prop["source_model"],
            }

    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

    # 5. Nếu không có món nào đạt ngưỡng >= 35% -> Yêu cầu chụp lại
    if not best_per_class:
        response = {
            "success": False,
            "require_retake": True,
            "message": "Không nhận diện rõ món ăn (độ chính xác dưới 35%). Vui lòng chụp lại ảnh gần và rõ nét hơn!",
            "image_size": {"width": img_width, "height": img_height},
            "inference_time_ms": elapsed_ms,
            "cnn_triggered_boxes": len(crops_for_cnn),
            "total_dishes": 0,
            "dishes": [],
        }
        logger.info("AI prediction response:\n%s", json.dumps(response, ensure_ascii=False, indent=2))
        return response

    # 6. Sắp xếp theo % giảm dần, gán mã màu và tính tọa độ trả về cho Frontend
    sorted_items = sorted(best_per_class.values(), key=lambda x: x["conf_raw"], reverse=True)
    dishes_output = []

    for idx, item in enumerate(sorted_items, start=1):
        x1, y1, x2, y2 = item["xyxy"]

        # Giới hạn tọa độ trong khung ảnh
        x1, y1 = max(0.0, x1), max(0.0, y1)
        x2, y2 = min(float(img_width), x2), min(float(img_height), y2)

        color = COLOR_PALETTE[(idx - 1) % len(COLOR_PALETTE)]

        dishes_output.append({
            "order": idx,
            "class_id": item["class_id"],
            "class_name": item["class_name"],
            "confidence": item["confidence"],
            "color": color,
            "source_model": item["source_model"],  # Giúp bạn theo dõi box nào do YOLO hay CNN quyết định
            "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
            "box_percent": {
                "left": round((x1 / img_width) * 100, 2),
                "top": round((y1 / img_height) * 100, 2),
                "width": round(((x2 - x1) / img_width) * 100, 2),
                "height": round(((y2 - y1) / img_height) * 100, 2),
            },
        })

    response = {
        "success": True,
        "require_retake": False,
        "message": f"Nhận diện thành công {len(dishes_output)} món ăn.",
        "image_size": {"width": img_width, "height": img_height},
        "inference_time_ms": elapsed_ms,
        "cnn_triggered_boxes": len(crops_for_cnn),
        "total_dishes": len(dishes_output),
        "dishes": dishes_output,
    }
    logger.info("AI prediction response:\n%s", json.dumps(response, ensure_ascii=False, indent=2))
    return response