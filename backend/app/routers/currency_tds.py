from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime, date
import logging

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.models.tally_core import MstLedger
from app.models.portal_core import Currency, SyncQueue
from app.models.portal_core import ExchangeRate, TdsSection, LowerDeductionCertificate, TdsTcsEntry
from sqlalchemy.orm import selectinload
from app.schemas.currency_tds import (
    CurrencyCreate, CurrencyResponse,
    ExchangeRateCreate, ExchangeRateResponse,
    TdsSectionCreate, TdsSectionResponse,
    LowerDeductionCertificateCreate, LowerDeductionCertificateResponse,
    TdsTcsEntryCreate, TdsTcsEntryResponse
)
from app.routers.sync import try_push_currency_realtime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Currency & TDS"])

# Comprehensive ISO 4217 seed data — all fields match the Currency DB model
SEED_CURRENCIES = [
    # South Asia
    {"code": "INR", "symbol": "INR", "formal_name": "Indian Rupee", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "paise", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "BDT", "symbol": "BDT", "formal_name": "Bangladeshi Taka", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "poisha", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "LKR", "symbol": "LKR", "formal_name": "Sri Lankan Rupee", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "NPR", "symbol": "NPR", "formal_name": "Nepalese Rupee", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "paisa", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "PKR", "symbol": "PKR", "formal_name": "Pakistani Rupee", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "paisa", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "MVR", "symbol": "MVR", "formal_name": "Maldivian Rufiyaa", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "laari", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "AFN", "symbol": "AFN", "formal_name": "Afghan Afghani", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "pul", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    # Americas
    {"code": "USD", "symbol": "USD", "formal_name": "US Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "CAD", "symbol": "CAD", "formal_name": "Canadian Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "BRL", "symbol": "BRL", "formal_name": "Brazilian Real", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "centavos", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "MXN", "symbol": "MXN", "formal_name": "Mexican Peso", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "centavos", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "ARS", "symbol": "ARS", "formal_name": "Argentine Peso", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "centavos", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "CLP", "symbol": "CLP", "formal_name": "Chilean Peso", "decimal_places": 0, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "", "decimal_places_for_words": 0, "show_amount_in_millions": False},
    {"code": "COP", "symbol": "COP", "formal_name": "Colombian Peso", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "centavos", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "PEN", "symbol": "PEN", "formal_name": "Peruvian Sol", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "céntimos", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "UYU", "symbol": "UYU", "formal_name": "Uruguayan Peso", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "centésimos", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "DOP", "symbol": "DOP", "formal_name": "Dominican Peso", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "centavos", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "JMD", "symbol": "JMD", "formal_name": "Jamaican Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "TTD", "symbol": "TTD", "formal_name": "Trinidad Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    # Europe
    {"code": "EUR", "symbol": "EUR", "formal_name": "Euro", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "GBP", "symbol": "GBP", "formal_name": "British Pound Sterling", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "pence", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "CHF", "symbol": "CHF", "formal_name": "Swiss Franc", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "centimes", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "SEK", "symbol": "SEK", "formal_name": "Swedish Krona", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "öre", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "NOK", "symbol": "NOK", "formal_name": "Norwegian Krone", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "øre", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "DKK", "symbol": "DKK", "formal_name": "Danish Krone", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "øre", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "PLN", "symbol": "PLN", "formal_name": "Polish Zloty", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "groszy", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "CZK", "symbol": "CZK", "formal_name": "Czech Koruna", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "haléřů", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "HUF", "symbol": "HUF", "formal_name": "Hungarian Forint", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "fillér", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "RON", "symbol": "RON", "formal_name": "Romanian Leu", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "bani", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "BGN", "symbol": "BGN", "formal_name": "Bulgarian Lev", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "stotinki", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "HRK", "symbol": "HRK", "formal_name": "Croatian Kuna", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "lipa", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "RSD", "symbol": "RSD", "formal_name": "Serbian Dinar", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "para", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "ISK", "symbol": "ISK", "formal_name": "Icelandic Krona", "decimal_places": 0, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "", "decimal_places_for_words": 0, "show_amount_in_millions": False},
    {"code": "UAH", "symbol": "UAH", "formal_name": "Ukrainian Hryvnia", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "kopiyok", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "RUB", "symbol": "RUB", "formal_name": "Russian Ruble", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "kopecks", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "TRY", "symbol": "TRY", "formal_name": "Turkish Lira", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "kuruş", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "GEL", "symbol": "GEL", "formal_name": "Georgian Lari", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "tetri", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "AMD", "symbol": "AMD", "formal_name": "Armenian Dram", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "luma", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "AZN", "symbol": "AZN", "formal_name": "Azerbaijani Manat", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "qəpik", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    # Middle East
    {"code": "AED", "symbol": "AED", "formal_name": "UAE Dirham", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "fils", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "SAR", "symbol": "SAR", "formal_name": "Saudi Riyal", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "halalas", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "QAR", "symbol": "QAR", "formal_name": "Qatari Riyal", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "dirhams", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "OMR", "symbol": "OMR", "formal_name": "Omani Rial", "decimal_places": 3, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "baisa", "decimal_places_for_words": 3, "show_amount_in_millions": False},
    {"code": "KWD", "symbol": "KWD", "formal_name": "Kuwaiti Dinar", "decimal_places": 3, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "fils", "decimal_places_for_words": 3, "show_amount_in_millions": False},
    {"code": "BHD", "symbol": "BHD", "formal_name": "Bahraini Dinar", "decimal_places": 3, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "fils", "decimal_places_for_words": 3, "show_amount_in_millions": False},
    {"code": "JOD", "symbol": "JOD", "formal_name": "Jordanian Dinar", "decimal_places": 3, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "fils", "decimal_places_for_words": 3, "show_amount_in_millions": False},
    {"code": "LBP", "symbol": "LBP", "formal_name": "Lebanese Pound", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "piastres", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "IQD", "symbol": "IQD", "formal_name": "Iraqi Dinar", "decimal_places": 3, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "fils", "decimal_places_for_words": 3, "show_amount_in_millions": False},
    {"code": "IRR", "symbol": "IRR", "formal_name": "Iranian Rial", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "dinars", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "ILS", "symbol": "ILS", "formal_name": "Israeli Shekel", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "agorot", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "EGP", "symbol": "EGP", "formal_name": "Egyptian Pound", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "piastres", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "MAD", "symbol": "MAD", "formal_name": "Moroccan Dirham", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "centimes", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    # East Asia
    {"code": "JPY", "symbol": "JPY", "formal_name": "Japanese Yen", "decimal_places": 0, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "", "decimal_places_for_words": 0, "show_amount_in_millions": True},
    {"code": "CNY", "symbol": "CNY", "formal_name": "Chinese Yuan", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "fen", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "KRW", "symbol": "KRW", "formal_name": "South Korean Won", "decimal_places": 0, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "", "decimal_places_for_words": 0, "show_amount_in_millions": True},
    {"code": "TWD", "symbol": "TWD", "formal_name": "Taiwan Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "MNT", "symbol": "MNT", "formal_name": "Mongolian Tugrik", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "möngö", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "HKD", "symbol": "HKD", "formal_name": "Hong Kong Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    # Southeast Asia
    {"code": "SGD", "symbol": "SGD", "formal_name": "Singapore Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "MYR", "symbol": "MYR", "formal_name": "Malaysian Ringgit", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "sen", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "THB", "symbol": "THB", "formal_name": "Thai Baht", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "satang", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "IDR", "symbol": "IDR", "formal_name": "Indonesian Rupiah", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "sen", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "PHP", "symbol": "PHP", "formal_name": "Philippine Peso", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "centavos", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "VND", "symbol": "VND", "formal_name": "Vietnamese Dong", "decimal_places": 0, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "", "decimal_places_for_words": 0, "show_amount_in_millions": False},
    {"code": "MMK", "symbol": "MMK", "formal_name": "Myanmar Kyat", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "pya", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "KHR", "symbol": "KHR", "formal_name": "Cambodian Riel", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "sen", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "LAK", "symbol": "LAK", "formal_name": "Lao Kip", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "att", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "BND", "symbol": "BND", "formal_name": "Brunei Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    # Oceania
    {"code": "AUD", "symbol": "AUD", "formal_name": "Australian Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "NZD", "symbol": "NZD", "formal_name": "New Zealand Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": True},
    {"code": "FJD", "symbol": "FJD", "formal_name": "Fijian Dollar", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "PGK", "symbol": "PGK", "formal_name": "Papua New Guinean Kina", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "toea", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    # Africa
    {"code": "ZAR", "symbol": "ZAR", "formal_name": "South African Rand", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "NGN", "symbol": "NGN", "formal_name": "Nigerian Naira", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "kobo", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "KES", "symbol": "KES", "formal_name": "Kenyan Shilling", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "GHS", "symbol": "GHS", "formal_name": "Ghanaian Cedi", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": False, "word_representing_amount_after_decimal": "pesewas", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "TZS", "symbol": "TZS", "formal_name": "Tanzanian Shilling", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "UGX", "symbol": "UGX", "formal_name": "Ugandan Shilling", "decimal_places": 0, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "", "decimal_places_for_words": 0, "show_amount_in_millions": False},
    {"code": "ETB", "symbol": "ETB", "formal_name": "Ethiopian Birr", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "santim", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "ZMW", "symbol": "ZMW", "formal_name": "Zambian Kwacha", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "ngwee", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "BWP", "symbol": "BWP", "formal_name": "Botswanan Pula", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "thebe", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "MUR", "symbol": "MUR", "formal_name": "Mauritian Rupee", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "SCR", "symbol": "SCR", "formal_name": "Seychellois Rupee", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "cents", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "XOF", "symbol": "XOF", "formal_name": "West African CFA Franc", "decimal_places": 0, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "", "decimal_places_for_words": 0, "show_amount_in_millions": False},
    {"code": "XAF", "symbol": "XAF", "formal_name": "Central African CFA Franc", "decimal_places": 0, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "", "decimal_places_for_words": 0, "show_amount_in_millions": False},
    # Central Asia
    {"code": "KZT", "symbol": "KZT", "formal_name": "Kazakhstani Tenge", "decimal_places": 2, "suffix_symbol_to_amount": False, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "tiyin", "decimal_places_for_words": 2, "show_amount_in_millions": False},
    {"code": "UZS", "symbol": "UZS", "formal_name": "Uzbekistani Som", "decimal_places": 2, "suffix_symbol_to_amount": True, "add_space_between_amount_and_symbol": True, "word_representing_amount_after_decimal": "tiyin", "decimal_places_for_words": 2, "show_amount_in_millions": False},
]


@router.post("/currency/seed")
async def seed_currencies(
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    """Bulk-insert world currencies into the DB. Skips any that already exist by code."""
    inserted = 0
    skipped = 0
    for c in SEED_CURRENCIES:
        existing = (await db.execute(select(Currency).where(Currency.code == c["code"]))).scalars().first()
        if existing:
            skipped += 1
            continue
        curr = Currency(
            code=c["code"],
            symbol=c["code"],
            formal_name=c["formal_name"],
            decimal_places=c["decimal_places"],
            show_amount_in_millions=c.get("show_amount_in_millions", False),
            suffix_symbol_to_amount=c.get("suffix_symbol_to_amount", False),
            add_space_between_amount_and_symbol=c.get("add_space_between_amount_and_symbol", True),
            word_representing_amount_after_decimal=c.get("word_representing_amount_after_decimal", ""),
            decimal_places_for_words=c.get("decimal_places_for_words", 2),
            is_base_currency=False
        )
        db.add(curr)
        inserted += 1
    await db.commit()
    return {"status": "success", "inserted": inserted, "skipped": skipped, "total_available": len(SEED_CURRENCIES)}

# --- Currencies ---

@router.post("/currency", response_model=CurrencyResponse)
async def create_currency(
    req: CurrencyCreate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.email} attempting to create currency: {req.code}")
    dup_query = await db.execute(select(Currency).where(Currency.code == req.code))
    if dup_query.scalars().first():
        logger.warning(f"Currency creation failed: Code {req.code} already exists.")
        raise HTTPException(status_code=400, detail="Currency code already exists.")
        
    currency = Currency(
        code=req.code,
        symbol=req.symbol,
        formal_name=req.formal_name,
        decimal_places=req.decimal_places,
        show_amount_in_millions=req.show_amount_in_millions,
        suffix_symbol_to_amount=req.suffix_symbol_to_amount,
        add_space_between_amount_and_symbol=req.add_space_between_amount_and_symbol,
        word_representing_amount_after_decimal=req.word_representing_amount_after_decimal,
        decimal_places_for_words=req.decimal_places_for_words,
        is_base_currency=req.is_base_currency
    )
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    
    # Process Rates
    if req.rates:
        for rate_req in req.rates:
            try:
                rdate = datetime.strptime(rate_req.rate_date, "%Y-%m-%d").date()
                rate = ExchangeRate(
                    company_id=user.company_id,
                    currency_id=currency.currency_id,
                    rate_date=rdate,
                    standard_rate=rate_req.standard_rate,
                    selling_rate=rate_req.selling_rate,
                    buying_rate=rate_req.buying_rate,
                    source=rate_req.source
                )
                db.add(rate)
            except ValueError:
                pass
        await db.commit()
        await db.refresh(currency)
        
    new_sq = SyncQueue(company_id=user.company_id, record_type="Currency", record_id=currency.currency_id, action="Create", is_processed=False)
    db.add(new_sq)
    await db.commit()
    
    logger.info(f"Currency {currency.code} created successfully. Added to SyncQueue (Create).")
    
    # Try pushing to Tally in real-time
    logger.info(f"Triggering real-time Tally push for Currency {currency.code} (Create)...")
    await try_push_currency_realtime(currency.currency_id, new_sq.sync_id, "Create", db)

    return currency

@router.put("/currency/{currency_id}", response_model=CurrencyResponse)
async def update_currency(
    currency_id: int,
    req: CurrencyCreate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.email} attempting to alter currency ID {currency_id} to code {req.code}")
    curr = (await db.execute(select(Currency).options(selectinload(Currency.rates)).where(Currency.currency_id == currency_id))).scalars().first()
    if not curr:
        logger.warning(f"Currency alter failed: Currency ID {currency_id} not found.")
        raise HTTPException(status_code=404, detail="Currency not found.")
        
    if curr.code != req.code:
        dup = (await db.execute(select(Currency).where(Currency.code == req.code))).scalars().first()
        if dup:
            logger.warning(f"Currency alter failed: Code {req.code} already exists.")
            raise HTTPException(status_code=400, detail="Currency code already exists.")
            
    curr.code = req.code
    curr.symbol = req.symbol
    curr.formal_name = req.formal_name
    curr.decimal_places = req.decimal_places
    curr.show_amount_in_millions = req.show_amount_in_millions
    curr.suffix_symbol_to_amount = req.suffix_symbol_to_amount
    curr.add_space_between_amount_and_symbol = req.add_space_between_amount_and_symbol
    curr.word_representing_amount_after_decimal = req.word_representing_amount_after_decimal
    curr.decimal_places_for_words = req.decimal_places_for_words
    curr.is_base_currency = req.is_base_currency
    
    if req.rates is not None:
        from sqlalchemy import delete
        await db.execute(delete(ExchangeRate).where(ExchangeRate.currency_id == currency_id, ExchangeRate.company_id == user.company_id))
        
        for rate_req in req.rates:
            try:
                rdate = datetime.strptime(rate_req.rate_date, "%Y-%m-%d").date()
                rate = ExchangeRate(
                    company_id=user.company_id,
                    currency_id=currency_id,
                    rate_date=rdate,
                    standard_rate=rate_req.standard_rate,
                    selling_rate=rate_req.selling_rate,
                    buying_rate=rate_req.buying_rate,
                    source=rate_req.source
                )
                db.add(rate)
            except ValueError:
                pass
                
    new_sq = SyncQueue(company_id=user.company_id, record_type="Currency", record_id=currency_id, action="Alter", is_processed=False)
    db.add(new_sq)
    await db.commit()
    await db.refresh(curr)
    
    logger.info(f"Currency {curr.code} (ID: {currency_id}) updated successfully. Added to SyncQueue (Alter).")
    
    # Try pushing to Tally in real-time
    logger.info(f"Triggering real-time Tally push for Currency {curr.code} (Alter)...")
    await try_push_currency_realtime(currency_id, new_sq.sync_id, "Alter", db)
    
    # Reload with new rates
    curr = (await db.execute(select(Currency).options(selectinload(Currency.rates)).where(Currency.currency_id == currency_id))).scalars().first()
    return curr

@router.get("/currency", response_model=List[CurrencyResponse])
async def get_currencies(
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    # Fetch all global currencies and eager load their exchange rates for the user's company
    res = await db.execute(select(Currency).options(selectinload(Currency.rates.and_(ExchangeRate.company_id == user.company_id))))
    return res.scalars().all()
    
@router.delete("/currency/{currency_id}")
async def delete_currency(
    currency_id: int,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.email} attempting to delete currency ID {currency_id}")
    curr = (await db.execute(select(Currency).where(Currency.currency_id == currency_id))).scalars().first()
    if not curr:
        logger.warning(f"Currency delete failed: Currency ID {currency_id} not found.")
        raise HTTPException(status_code=404, detail="Currency not found.")
        
    code = curr.code
    curr_symbol = curr.symbol
    new_sq = SyncQueue(company_id=user.company_id, record_type="Currency", record_id=currency_id, action="Delete", is_processed=False)
    db.add(new_sq)
    await db.delete(curr)
    await db.commit()
    
    logger.info(f"Currency {code} (ID: {currency_id}) deleted successfully. Added to SyncQueue (Delete).")
    
    # Try pushing to Tally in real-time
    logger.info(f"Triggering real-time Tally push for Currency {code} (Delete)...")
    await try_push_currency_realtime(currency_id, new_sq.sync_id, "Delete", db, deleted_symbol=curr_symbol, deleted_code=code)
    
    return {"message": "Currency deleted successfully"}

# --- TDS Sections ---

@router.get("/tds/sections", response_model=List[TdsSectionResponse])
async def get_tds_sections(
    user: User = Depends(require_permission("settings", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TdsSection).where(TdsSection.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/tds/sections", response_model=TdsSectionResponse)
async def create_tds_section(
    req: TdsSectionCreate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    dup_query = await db.execute(
        select(TdsSection).where(
            TdsSection.company_id == user.company_id,
            TdsSection.section_code == req.section_code
        )
    )
    if dup_query.scalars().first():
        raise HTTPException(status_code=400, detail="TDS Section already exists.")
        
    section = TdsSection(
        company_id=user.company_id,
        section_code=req.section_code,
        description=req.description,
        default_rate_percent=req.default_rate_percent,
        threshold_limit=req.threshold_limit
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section

# --- Lower Deduction Certificates ---

@router.get("/tds/certificates", response_model=List[LowerDeductionCertificateResponse])
async def get_ldcs(
    user: User = Depends(require_permission("settings", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(LowerDeductionCertificate).join(MstLedger, LowerDeductionCertificate.party_ledger_id == MstLedger.ledger_id).where(MstLedger.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/tds/certificates", response_model=LowerDeductionCertificateResponse)
async def create_ldc(
    req: LowerDeductionCertificateCreate,
    user: User = Depends(require_permission("settings", "create")),
    db: AsyncSession = Depends(get_db)
):
    try:
        from_date = datetime.strptime(req.valid_from, "%Y-%m-%d").date()
        to_date = datetime.strptime(req.valid_to, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    # Verify ledger
    ledg_query = await db.execute(
        select(MstLedger).where(MstLedger.ledger_id == req.party_ledger_id, MstLedger.company_id == user.company_id)
    )
    if not ledg_query.scalars().first():
        raise HTTPException(status_code=400, detail="Party ledger not found.")
        
    # Verify section
    sec_query = await db.execute(
        select(TdsSection).where(TdsSection.section_id == req.section_id, TdsSection.company_id == user.company_id)
    )
    if not sec_query.scalars().first():
        raise HTTPException(status_code=400, detail="TDS Section not found.")
        
    ldc = LowerDeductionCertificate(
        party_ledger_id=req.party_ledger_id,
        section_id=req.section_id,
        certificate_number=req.certificate_number,
        reduced_rate_percent=req.reduced_rate_percent,
        valid_from=from_date,
        valid_to=to_date
    )
    db.add(ldc)
    await db.commit()
    await db.refresh(ldc)
    return ldc

# --- TDS Resolver ---

@router.get("/tds/resolve-rate/{party_ledger_id}/{section_id}")
async def resolve_tds_rate(
    party_ledger_id: int,
    section_id: int,
    check_date: Optional[str] = None,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    if check_date:
        try:
            target_date = datetime.strptime(check_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    else:
        target_date = date.today()
        
    # Verify section
    sec_query = await db.execute(
        select(TdsSection).where(TdsSection.section_id == section_id, TdsSection.company_id == user.company_id)
    )
    section = sec_query.scalars().first()
    if not section:
        raise HTTPException(status_code=400, detail="TDS Section not found.")
        
    # Check LDC
    ldc_query = await db.execute(
        select(LowerDeductionCertificate).where(
            LowerDeductionCertificate.party_ledger_id == party_ledger_id,
            LowerDeductionCertificate.section_id == section_id,
            LowerDeductionCertificate.valid_from <= target_date,
            LowerDeductionCertificate.valid_to >= target_date
        )
    )
    ldc = ldc_query.scalars().first()
    
    if ldc:
        return {
            "rate_percent": float(ldc.reduced_rate_percent),
            "certificate_id": ldc.certificate_id,
            "source": "Certificate"
        }
        
    return {
        "rate_percent": float(section.default_rate_percent),
        "certificate_id": None,
        "source": "Default"
    }

# --- TDS Entries ---

@router.post("/tds/entries", response_model=TdsTcsEntryResponse)
async def create_tds_entry(
    req: TdsTcsEntryCreate,
    user: User = Depends(require_permission("vouchers", "create")),
    db: AsyncSession = Depends(get_db)
):
    try:
        ddate = datetime.strptime(req.deduction_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    entry = TdsTcsEntry(
        company_id=user.company_id,
        entry_type=req.entry_type,
        voucher_id=req.voucher_id,
        party_ledger_id=req.party_ledger_id,
        section_id=req.section_id,
        taxable_amount=req.taxable_amount,
        rate_percent_applied=req.rate_percent_applied,
        tax_amount=req.tax_amount,
        certificate_id=req.certificate_id,
        deduction_date=ddate
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry
