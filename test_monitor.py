"""Smoke tests for deal title classification; no network or Telegram required."""
import unittest

from monitor import apple_product_type, classify


class AppleRulesTest(unittest.TestCase):
    def test_macbook_without_discount_keyword(self):
        self.assertEqual(classify("[쿠팡] 맥북 에어 M4 1,199,000원"), "애플 맥북 특가 제보")

    def test_iphone_english(self):
        self.assertEqual(classify("[쿠팡] iPhone 17 256GB"), "애플 아이폰 특가 제보")

    def test_ipad_price_error(self):
        self.assertEqual(classify("아이패드 프로 가격오류"), "애플 아이패드 가격 오류 의심")

    def test_airpods_price(self):
        self.assertEqual(apple_product_type("에어팟 프로 2세대"), "에어팟")

    def test_accessories_excluded(self):
        for title in ["애플워치 스트랩 할인", "아이폰 케이스", "맥북 충전기"]:
            with self.subTest(title=title):
                self.assertIsNone(classify(title))

    def test_accessory_price_error_still_general(self):
        self.assertEqual(classify("아이폰 케이스 가격실수"), "가격 오류 의심")

    def test_general_hot_deal_still_works(self):
        self.assertEqual(classify("갤럭시 버즈 역대가"), "초특가 제보")

    def test_sold_out_has_priority(self):
        self.assertIsNone(classify("[품절] 아이폰 17 가격오류"))

    def test_plain_title_is_ignored(self):
        self.assertIsNone(classify("오늘 배송 관련 안내"))


if __name__ == "__main__":
    unittest.main()
