# app/api/public/routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import yfinance as yf
from datetime import datetime, timedelta
import pytz
from ...db.database import get_db
from ...models.models import CompanyInfo
from .schemas import CompanyInfoResponse, CompanySymbolsResponse

ALPHA_VANTAGE_API_KEY = "ZACILF0TUXI6H5BN"

router = APIRouter()

# List of IDX stock symbols
IDX_STOCKS = [
    "AALI", "ABBA", "ABDA", "ABMM", "ACES", "ACST", "ADES", "ADHI", "ADMF", "ADMG", 
    "ADRO", "AGII", "AGRO", "AGRS", "AHAP", "AIMS", "AISA", "AKKU", "AKPI", "AKRA", 
    "AKSI", "ALDO", "ALKA", "ALMI", "ALTO", "AMAG", "AMFG", "AMIN", "AMRT", "ANJT", 
    "ANTM", "APEX", "APIC", "APII", "APLI", "APLN", "ARGO", "ARII", "ARNA", "ARTA", 
    "ARTI", "ARTO", "ASBI", "ASDM", "ASGR", "ASII", "ASJT", "ASMI", "ASRI", "ASRM", 
    "ASSA", "ATIC", "AUTO", "BABP", "BACA", "BAJA", "BALI", "BAPA", "BATA", "BAYU", 
    "BBCA", "BBHI", "BBKP", "BBLD", "BBMD", "BBNI", "BBRI", "BBRM", "BBTN", "BBYB", 
    "BCAP", "BCIC", "BCIP", "BDMN", "BEKS", "BEST", "BFIN", "BGTG", "BHIT", "BIKA", 
    "BIMA", "BINA", "BIPI", "BIPP", "BIRD", "BISI", "BJBR", "BJTM", "BKDP", "BKSL", 
    "BKSW", "BLTA", "BLTZ", "BMAS", "BMRI", "BMSR", "BMTR", "BNBA", "BNBR", "BNGA", 
    "BNII", "BNLI", "BOLT", "BPFI", "BPII", "BRAM", "BRMS", "BRNA", "BRPT", "BSDE", 
    "BSIM", "BSSR", "BSWD", "BTEK", "BTEL", "BTON", "BTPN", "BUDI", "BUKK", "BULL", 
    "BUMI", "BUVA", "BVIC", "BWPT", "BYAN", "CANI", "CASS", "CEKA", "CENT", "CFIN", 
    "CINT", "CITA", "CLPI", "CMNP", "CMPP", "CNKO", "CNTX", "COWL", "CPIN", "CPRO", 
    "CSAP", "CTBN", "CTRA", "CTTH", "DART", "DEFI", "DEWA", "DGIK", "DILD", "DKFT", 
    "DLTA", "DMAS", "DNAR", "DNET", "DOID", "DPNS", "DSFI", "DSNG", "DSSA", "DUTI", 
    "DVLA", "DYAN", "ECII", "EKAD", "ELSA", "ELTY", "EMDE", "EMTK", "ENRG", "EPMT", 
    "ERAA", "ERTX", "ESSA", "ESTI", "ETWA", "EXCL", "FAST", "FASW", "FISH", "FMII", 
    "FORU", "FPNI", "FREN", "GAMA", "GDST", "GDYR", "GEMA", "GEMS", "GGRM", "GIAA", 
    "GJTL", "GLOB", "GMTD", "GOLD", "GOLL", "GPRA", "GSMF", "GTBO", "GWSA", "GZCO", 
    "HADE", "HDFA", "HDTX", "HERO", "HEXA", "HITS", "HMSP", "HOME", "HOTL", "HRUM", 
    "IATA", "IBFN", "IBST", "ICBP", "ICON", "IGAR", "IIKP", "IKAI", "IKBI", "IMAS", 
    "IMJS", "IMPC", "INAF", "INAI", "INCI", "INCO", "INDF", "INDR", "INDS", "INDX", 
    "INDY", "INKP", "INPC", "INPP", "INRU", "INTA", "INTD", "INTP", "JIHD", "JKON", 
    "JKSW", "JPFA", "JRPT", "JSMR", "JSPT", "JTPE", "KAEF", "KARW", "KBLI", "KBLM", 
    "KBLV", "KBRI", "KDSI", "KIAS", "KICI", "KIJA", "KKGI", "KLBF", "KOBX", "KOIN", 
    "KONI", "KOPI", "KPIG", "KRAH", "KRAS", "KREN", "LAPD", "LCGP", "LEAD", "LINK", 
    "LION", "LMAS", "LMPI", "LMSH", "LPCK", "LPGI", "LPIN", "LPKR", "LPLI", "LPPF", 
    "LPPS", "LRNA", "LSIP", "LTLS", "MAGP", "MAIN", "MAMI", "MAPI", "MASA", "MAYA", 
    "MBAP", "MBSS", "MBTO", "MCOR", "MDIA", "MDKA", "MDLN", "MDRN", "MEDC", "MEGA", 
    "MERK", "META", "MFIN", "MFMI", "MGNA", "MICE", "MIDI", "MIKA", "MIRA", "MITI", 
    "MKPI", "MLBI", "MLIA", "MLPL", "MLPT", "MMLP", "MNCN", "MPMX", "MPPA", "MRAT", 
    "MREI", "MSKY", "MTDL", "MTFN", "MTLA", "MTSM", "MYOH", "MYOR", "MYRX", "MYTX", 
    "NELY", "NIKL", "NIPS", "NIRO", "NISP", "NOBU", "NRCA", "OCAP", "OKAS", "OMRE", 
    "PADI", "PALM", "PANR", "PANS", "PBRX", "PDES", "PEGE", "PGAS", "PGLI", "PICO", 
    "PJAA", "PKPK", "PLAS", "PLIN", "PNBN", "PNBS", "PNIN", "PNLF", "PNSE", "POLY", 
    "POOL", "PPRO", "PRAS", "PSAB", "PSDN", "PSKT", "PTBA", "PTIS", "PTPP", "PTRO", 
    "PTSN", "PTSP", "PUDP", "PWON", "PYFA", "RIMO", "RODA", "ROTI", "RUIS", "SAFE", 
    "SAME", "SCCO", "SCMA", "SCPI", "SDMU", "SDPC", "SDRA", "SGRO", "SHID", "SIDO", 
    "SILO", "SIMA", "SIMP", "SIPD", "SKBM", "SKLT", "SKYB", "SMAR", "SMBR", "SMCB", 
    "SMDM", "SMDR", "SMGR", "SMMA", "SMMT", "SMRA", "SMRU", "SMSM", "SOCI", "SONA", 
    "SPMA", "SQMI", "SRAJ", "SRIL", "SRSN", "SRTG", "SSIA", "SSMS", "SSTM", "STAR", 
    "STTP", "SUGI", "SULI", "SUPR", "TALF", "TARA", "TAXI", "TBIG", "TBLA", "TBMS", 
    "TCID", "TELE", "TFCO", "TGKA", "TIFA", "TINS", "TIRA", "TIRT", "TKIM", "TLKM", 
    "TMAS", "TMPO", "TOBA", "TOTL", "TOTO", "TOWR", "TPIA", "TPMA", "TSPC", "ULTJ", 
    "UNIC", "UNIT", "UNSP", "UNTR", "UNVR", "VICO", "VINS", "VIVA", "VOKS", "VRNA", 
    "WAPO", "WEHA", "WICO", "WIIM", "WIKA", "WINS", "WOMF", "WSKT", "WTON", "YPAS", 
    "YULE", "ZBRA", "SHIP", "CASA", "DAYA", "DPUM", "IDPR", "JGLE", "KINO", "MARI", 
    "MKNT", "MTRA", "PRDA", "BOGA", "BRIS", "PORT", "CARS", "MINA", "FORZ", "CLEO", 
    "TAMU", "CSIS", "TGRA", "FIRE", "TOPS", "KMTR", "ARMY", "MAPB", "WOOD", "HRTA", 
    "MABA", "HOKI", "MPOW", "MARK", "NASA", "MDKI", "BELL", "KIOS", "GMFI", "MTWI", 
    "ZINC", "MCAS", "PPRE", "WEGE", "PSSI", "MORA", "DWGL", "PBID", "JMAS", "CAMP", 
    "IPCM", "PCAR", "LCKM", "BOSS", "HELI", "JSKY", "INPS", "GHON", "TDPM", "DFAM", 
    "NICK", "BTPS", "SPTO", "PRIM", "HEAL", "TRUK", "PZZA", "TUGU", "MSIN", "SWAT", 
    "KPAL", "TNCA", "MAPA", "TCPI", "IPCC", "RISE", "BPTR", "POLL", "NFCX", "MGRO", 
    "NUSA", "FILM", "ANDI", "LAND", "MOLI", "PANI", "DIGI", "CITY", "SAPX", "KPAS", 
    "SURE", "HKMU", "MPRO", "DUCK", "GOOD", "SKRN", "YELO", "CAKK", "SATU", "SOSS", 
    "DEAL", "POLA", "DIVA", "LUCK", "URBN", "SOTS", "ZONE", "PEHA", "FOOD", "BEEF", 
    "POLI", "CLAY", "NATO", "JAYA", "COCO", "MTPS", "CPRI", "HRME", "POSA", "JAST", 
    "FITT", "BOLA", "CCSI", "SFAN", "POLU", "KJEN", "KAYU", "ITIC", "PAMG", "IPTV", 
    "BLUE", "ENVY", "EAST", "LIFE", "FUJI", "KOTA", "INOV", "ARKA", "SMKL", "HDIT", 
    "KEEN", "BAPI", "TFAS", "GGRP", "OPMS", "NZIA", "SLIS", "PURE", "IRRA", "DMMX", 
    "SINI", "WOWS", "ESIP", "TEBE", "KEJU", "PSGO", "AGAR", "IFSH", "REAL", "IFII", 
    "PMJS", "UCID", "GLVA", "PGJO", "AMAR", "CSRA", "INDO", "AMOR", "TRIN", "DMND", 
    "PURA", "PTPW", "TAMA", "IKAN", "AYLS", "DADA", "ASPI", "ESTA", "BESS", "AMAN", 
    "CARE", "SAMF", "SBAT", "KBAG", "CBMF", "RONY", "CSMI", "BBSS", "BHAT", "CASH", 
    "TECH", "EPAC", "UANG", "PGUN", "SOFA", "PPGL", "TOYS", "SGER", "TRJA", "PNGO", 
    "SCNP", "BBSI", "KMDS", "PURI", "SOHO", "HOMI", "ROCK", "ENZO", "PLAN", "PTDU", 
    "ATAP", "VICI", "PMMP", "WIFI", "FAPA", "DCII", "KETR", "DGNS", "UFOE", "BANK", 
    "WMUU", "EDGE", "UNIQ", "BEBS", "SNLK", "ZYRX", "LFLO", "FIMP", "TAPG", "NPGF", 
    "LUCY", "ADCP", "HOPE", "MGLV", "TRUE", "LABA", "BUKA", "HAIS", "OILS", "GPSO", 
    "MCOL", "MTEL", "DEPO", "BINO", "CMRY", "WGSH", "TAYS", "WMPP", "RMKE", "OBMD", 
    "AVIA", "IPPE", "NASI", "BSML", "DRMA", "ADMR", "SEMA", "ASLC", "NETV", "BAUT", 
    "ENAK", "NTBK", "BIKE", "WIRG", "SICO", "GOTO", "TLDN", "MTMH", "WINR", "IBOS", 
    "OLIV", "ASHA", "SWID", "TRGU", "ARKO", "CHEM", "DEWI", "AXIO", "KRYA", "HATM", 
    "RCCC", "GULA", "JARR", "AMMS", "RAFI", "KKES", "ELPI", "EURO", "KLIN", "TOOL", "BUAH", "CRAB", 
    "MEDS", "COAL", "PRAY", "CBUT", "BELI", "MKTR", "OMED", "BSBK", "PDPP", "KDTN", 
    "SOUL", "ELIT", "BEER", "CBPE", "SUNI", "CBRE", "WINE", "BMBL", "PEVE", "LAJU", 
    "FWCT", "NAYZ", "IRSX", "PACK", "VAST", "CHIP", "HALO", "KING", "PGEO", "FUTR", 
    "GTRA", "HAJJ", "PIPA", "NCKL", "MENN", "AWAN", "MBMA", "RAAM", "DOOH", "JATI", 
    "TYRE", "MPXL", "SMIL", "KLAS", "MAXI", "VKTR", "RELF", "AMMN", "CRSN", "HBAT", 
    "GRIA", "PPRI", "ERAL", "CYBR", "MUTU", "LMAX", "KOCI", "PTPS", "BREN", "STRK", 
    "KOKA", "LOPI", "UDNG", "CGAS", "NICE", "MSJA", "SMLE", "ACRO", "MANG", "MEJA", 
    "LIVE", "HYGN", "BAIK", "VISI", "AREA", "MHKI", "ATLA", "DATA", "SOLA", "BATR", 
    "SPRE", "PART", "GOLF", "ISEA", "BLES", "GUNA", "LABS", "DOSS", "NEST", "PTMR", 
    "VERN", "DAAZ", "BOAT", "OASA", "POWR", "INCF", "WSBP", "PBSA", "IPOL", "ISAT", 
    "ISSP", "ITMA", "ITMG", "JAWA", "JECC", "NAIK", "AADI", "MDIY", "TRAM", "TRIL", 
    "TRIM", "TRIO", "TRIS", "TRST", "TRUS", "RSGK", "RUNS", "SBMA", "CMNT", "GTSI", 
    "IDEA", "KUAS", "BOBA", "GRPM", "WIDI", "TGUK", "INET", "MAHA", "RMKO", "CNMA", 
    "FOLK", "HUMI", "MSIE", "RSCH", "BABY", "AEGS", "IOTF", "RGAS", "MSTI", "IKPM", 
    "AYAM", "SURI", "ASLI", "GRPH", "SMGA", "UNTD", "TOSK", "MPIX", "ALII", "MKAP", 
    "SMKM", "STAA", "NANO", "ARCI", "IPAC", "MASB", "BMHS", "FLMC", "NICL", "UVCR", 
    "ZATA", "NINE", "MMIX", "PADA", "ISAP", "VTNY", "HILL", "BDKR", "PTMP", "SAGE", 
    "TRON", "CUAN", "NSSS", "RAJA", "RALS", "RANC", "RBMS", "RDTX", "RELI", "RICY", 
    "RIGS"
]

@router.get("/")
async def public_route():
    return {"message": "This is a public endpoint"}

@router.get("/companies/symbols", response_model=CompanySymbolsResponse)
async def get_idx_symbols():
    """Get all IDX Composite ticker symbols"""
    return CompanySymbolsResponse(
        symbols=IDX_STOCKS,
        count=len(IDX_STOCKS)
    )

@router.get("/companies/{symbol}", response_model=CompanyInfoResponse)
async def get_company_info(symbol: str, db: Session = Depends(get_db)):
    """Get detailed information for a specific company"""
    try:
        # Check if symbol exists
        if symbol not in IDX_STOCKS:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in IDX Composite")

        # Check if we have cached data less than 1 day old
        utc_now = datetime.now(pytz.UTC)
        oldest_allowed_date = utc_now - timedelta(days=1)
        
        # Try to get company from cache
        company_info = db.query(CompanyInfo).filter(CompanyInfo.symbol == symbol).first()
        
        # If we have recent cached data, return it
        if company_info and company_info.last_updated.replace(tzinfo=pytz.UTC) > oldest_allowed_date:
            return company_info

        # If no cached data or cache is old, fetch new data
        try:
            # Create or update company info
            if not company_info:
                company_info = CompanyInfo(symbol=symbol)
                db.add(company_info)

            company_info.last_updated = utc_now

            # Try to fetch additional data from yfinance
            yf_stock = yf.Ticker(f"{symbol}.JK")
            info = yf_stock.info

            # Update fields
            if info:
                company_info.company_name = info.get('longName', symbol)
                company_info.sector = info.get('sector')
                company_info.industry = info.get('industry')
                company_info.market_cap = info.get('marketCap')
                company_info.description = info.get('longBusinessSummary')

            # Commit changes
            db.commit()
            return company_info

        except Exception as e:
            db.rollback()
            # If we have old cached data, return it rather than failing
            if company_info:
                return company_info
            raise HTTPException(
                status_code=500, 
                detail=f"Error fetching company data: {str(e)}"
            )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )