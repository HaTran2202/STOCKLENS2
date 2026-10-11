# Financial data export

All statement CSV files use wide format: one row represents one ticker and reporting period; each financial item is a separate column.
Statement-variable columns are the original Vietcap codes (`isa*`, `isb*`, `bsa*`, `cfa*`, `cfb*`). Their human-readable labels are listed under each CSV section below.
Values are reported in VND unless otherwise noted. Blank values mean the source did not provide a value for that period.
For annual rows, `quarter` is empty. In `Stock Metrics History.csv`, annual observations use `quarter = 5`.

## Stock metrics

`Stock Metrics.csv` contains the latest available snapshot. `Stock Metrics History.csv` contains the selected annual and/or quarterly history.
Multiples such as `pe` and `pb` are expressed in x. Rate fields such as `roe`, `roa`, margins, NIM, CIR, CAR, CASA, NPL and LDR are decimal ratios (for example `0.15` means 15%).

### Stock Metrics.csv

Current snapshot fields include `ticker` and the following fields when available:

| CSV column | Original name |
| --- | --- |
| `period_date` | Kỳ dữ liệu |
| `pe` | P/E |
| `pb` | P/B |
| `ps` | P/S |
| `price_to_cash_flow` | P/CF |
| `ev_to_ebitda` | EV/EBITDA |
| `roe` | ROE |
| `roa` | ROA |
| `gross_margin` | Biên lợi nhuận gộp |
| `pre_tax_margin` | Biên lợi nhuận trước thuế |
| `after_tax_margin` | Biên lợi nhuận sau thuế |
| `debt_to_equity` | Nợ/Vốn chủ sở hữu |
| `financial_leverage` | Đòn bẩy tài chính |
| `current_ratio` | Hệ số thanh toán hiện hành |
| `quick_ratio` | Hệ số thanh toán nhanh |
| `cash_ratio` | Hệ số tiền mặt |
| `asset_turnover` | Vòng quay tài sản |
| `market_cap` | Vốn hóa thị trường |
| `shares` | Số cổ phiếu lưu hành |
| `net_interest_margin` | NIM |
| `cir` | CIR |
| `car` | CAR |
| `casa_ratio` | CASA |
| `npl` | Nợ xấu (NPL) |
| `ldr` | LDR |
| `loans_growth` | Tăng trưởng tín dụng |
| `deposit_growth` | Tăng trưởng tiền gửi |

### Stock Metrics History.csv

Historical fields include `ticker`, `year_report`, `quarter_report`, and the following fields when available:

| CSV column | Original name |
| --- | --- |
| `period_date` | Kỳ dữ liệu |
| `pe` | P/E |
| `pb` | P/B |
| `ps` | P/S |
| `price_to_cash_flow` | P/CF |
| `ev_to_ebitda` | EV/EBITDA |
| `roe` | ROE |
| `roa` | ROA |
| `gross_margin` | Biên lợi nhuận gộp |
| `pre_tax_margin` | Biên lợi nhuận trước thuế |
| `after_tax_margin` | Biên lợi nhuận sau thuế |
| `debt_to_equity` | Nợ/Vốn chủ sở hữu |
| `financial_leverage` | Đòn bẩy tài chính |
| `current_ratio` | Hệ số thanh toán hiện hành |
| `quick_ratio` | Hệ số thanh toán nhanh |
| `cash_ratio` | Hệ số tiền mặt |
| `asset_turnover` | Vòng quay tài sản |
| `market_cap` | Vốn hóa thị trường |
| `shares` | Số cổ phiếu lưu hành |
| `net_interest_margin` | NIM |
| `cir` | CIR |
| `car` | CAR |
| `casa_ratio` | CASA |
| `npl` | Nợ xấu (NPL) |
| `ldr` | LDR |
| `loans_growth` | Tăng trưởng tín dụng |
| `deposit_growth` | Tăng trưởng tiền gửi |

## Cash Flow.csv

All financial data columns use the original Vietcap field code exactly. The table below maps each code to its display label.

| Vietcap field code / CSV column | Display label |
| --- | --- |
| `cfa1` | Lợi nhuận/(lỗ) trước thuế |
| `cfa10` | (Tăng)/giảm các khoản phải thu |
| `cfa103` | Phân bổ lợi thế thương mại |
| `cfa104` | Các khoản điều chỉnh khác |
| `cfa105` | (Tăng)/giảm chứng khoán kinh doanh |
| `cfa11` | (Tăng)/giảm hàng tồn kho |
| `cfa12` | Tăng/(giảm) các khoản phải trả |
| `cfa13` | (Tăng)/giảm chi phí trả trước |
| `cfa14` | Tiền lãi vay đã trả |
| `cfa15` | Thuế thu nhập doanh nghiệp đã nộp |
| `cfa16` | Tiền thu khác từ hoạt động kinh doanh |
| `cfa17` | Tiền chi khác cho hoạt động kinh doanh |
| `cfa18` | Lưu chuyển tiền tệ ròng từ các hoạt động sản xuất kinh doanh |
| `cfa19` | Tiền chi để mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác |
| `cfa2` | Khấu hao TSCĐ và BĐSĐT |
| `cfa20` | Tiền thu từ thanh lý, nhượng bán TSCĐ và các tài sản dài hạn khác |
| `cfa21` | Tiền chi cho vay, mua các công cụ nợ của đơn vị khác |
| `cfa22` | Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác |
| `cfa23` | Tiền chi đầu tư góp vốn vào đơn vị khác |
| `cfa24` | Tiền thu hồi đầu tư góp vốn vào đơn vị khác |
| `cfa25` | Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia |
| `cfa26` | Lưu chuyển tiền thuần từ hoạt động đầu tư |
| `cfa27` | Tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu |
| `cfa28` | Tiền chi trả vốn góp cho các chủ sở hữu, mua lại cổ phiếu của doanh nghiệp đã phát hành |
| `cfa29` | Tiền thu được các khoản đi vay |
| `cfa3` | Chi phí dự phòng |
| `cfa30` | Tiền trả nợ gốc vay |
| `cfa31` | Tiền trả nợ gốc thuê tài chính |
| `cfa32` | Cổ tức, lợi nhuận đã trả cho chủ sở hữu |
| `cfa33` | Tiền lãi đã nhận |
| `cfa34` | Lưu chuyển tiền thuần từ hoạt động tài chính |
| `cfa35` | Lưu chuyển tiền thuần trong kỳ |
| `cfa36` | Tiền và tương đương tiền đầu kỳ |
| `cfa37` | Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ |
| `cfa38` | Tiền và tương đương tiền cuối kỳ |
| `cfa39` | cfa39 |
| `cfa4` | Lãi/lỗ chênh lệch tỷ giá hối đoái do đánh giá lại các khoản mục tiền tệ có gốc ngoại tệ |
| `cfa40` | cfa40 |
| `cfa41` | cfa41 |
| `cfa42` | cfa42 |
| `cfa43` | Tiền thuế thu nhập thực nộp trong kỳ |
| `cfa44` | cfa44 |
| `cfa45` | cfa45 |
| `cfa5` | Lãi/(lỗ) từ thanh lý tài sản cố định |
| `cfa6` | (Lãi)/lỗ từ hoạt động đầu tư |
| `cfa7` | Chi phí lãi vay |
| `cfa8` | Thu lãi và cổ tức |
| `cfa9` | Lợi nhuận/(lỗ) từ hoạt động kinh doanh trước những thay đổi vốn lưu động |
| `cfb106` | Tiền thu các khoản nợ đã được xử lý, xóa, bù đắp bằng nguồn rủi ro |
| `cfb221` | Chênh lệch số tiền thực thu/thực chi từ hoạt động kinh doanh |
| `cfb49` | Tăng/giảm các khoản tiền gửi và cho vay các tổ chức tín dụng khác |
| `cfb50` | Tăng/giảm chứng khoán kinh doanh (Trước năm 2016) |
| `cfb51` | Tăng/giảm các công cụ tài chính phái sinh và các tài sản tài chính khác |
| `cfb52` | Tăng/giảm các khoản cho vay khách hàng |
| `cfb54` | Tăng/giảm nguồn dự phòng để bù đắp tổn thất các khoản |
| `cfb55` | Tăng/giảm khác về tài sản hoạt động |
| `cfb56` | Tăng/(Giảm) các khoản nợ chính phủ và NHNN |
| `cfb57` | Tăng/(Giảm) các khoản tiền gửi và vay các TCTD khác |
| `cfb58` | Tăng/(Giảm) tiền gửi của khách hàng |
| `cfb59` | Tăng/(Giảm) các công cụ tài chính phái sinh và các khoản nợ tài chính khác |
| `cfb60` | Tăng/(Giảm) vốn tài trợ, uỷ thác đầu tư của chính phủ và các TCTD khác |
| `cfb61` | Tăng/(Giảm) phát hành giấy tờ có giá |
| `cfb63` | Tăng/(Giảm) khác về công nợ hoạt động |
| `cfb64` | Lưu chuyển tiền thuần từ hoạt động kinh doanh trước thuế thu nhập DN |
| `cfb65` | Chi từ các quỹ của TCTD |
| `cfb67` | Tiền chi từ thanh lý, nhượng bán TSCĐ |
| `cfb68` | Mua sắm Bất động sản đầu tư |
| `cfb69` | Tiền thu từ bán, thanh lý bất động sản đầu tư |
| `cfb71` | Tiền thu từ phát hành giấy tờ có giá dài hạn đủ điều kiện tính vào vốn tự có và các khoản vốn vay dài hạn khác |
| `cfb72` | Tiền chi thanh toán giấy tờ có giá dài hạn đủ điều kiện tính vào vốn tự có và các khoản vốn vay dài hạn khác |
| `cfb73` | Tiền chi ra mua cổ phiếu quỹ |
| `cfb74` | Tiền thu được do bán cổ phiếu quỹ |
| `cfb75` | Thu nhập lãi và các khoản thu nhập tương tự nhận được |
| `cfb76` | Chi phí lãi và các chi phí tương tự đã trả |
| `cfb77` | Thu nhập từ hoạt động dịch vụ nhận được |
| `cfb78` | Thu nhập thuần từ hoạt động kinh doanh ngoại hối và vàng |
| `cfb79` | Thu nhập từ hoạt động kinh doanh chứng khoán |
| `cfb80` | Thu nhập khác |
| `cfb81` | Tiền chi trả cho nhân viên và hoạt động quản lý, cộng cụ |
| `cfi92` | Phải thu hoạt động khác |
| `cfi97` | Phải trả hoạt động khác |
| `cfi99` | cfi99 |
| `cfs107` | cfs107 |
| `cfs108` | cfs108 |
| `cfs109` | cfs109 |
| `cfs110` | cfs110 |
| `cfs111` | cfs111 |
| `cfs112` | cfs112 |
| `cfs114` | Tiền vay khác |
| `cfs116` | Tiền chi trả nợ gốc vay tài sản tài chính |
| `cfs117` | Tiền chi trả gốc nợ vay khác |
| `cfs118` | Tiền mặt, tiền gửi ngân hàng đầu kỳ |
| `cfs120` | Các khoản tương đương tiền |
| `cfs121` | Tiền mặt, tiền gửi ngân hàng kỳ |
| `cfs123` | Các khoản tương đương tiền |
| `cfs124` | Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ |
| `cfs125` | Tiền thu bán chứng khoán môi giới cho khách hàng |
| `cfs126` | Tiền chi mua chứng khoán môi giới cho khách hàng |
| `cfs127` | Tiền thu bán chứng khoán ủy thác của khách hàng |
| `cfs128` | Tiền chi bán chứng khoán ủy thác của khách hàng |
| `cfs129` | Thu tiền từ tài khoản vãng lai của khách hàng (Trước năm 2016) |
| `cfs130` | Chi tiền từ tài khoản vãng lai của khách hàng (Trước năm 2016) |
| `cfs133` | Nhận tiền gửi để thanh toán giao dịch chứng khoán của khách hàng |
| `cfs134` | Nhận tiền gửi của Nhà đầu tư cho hoạt động ủy thác đầu tư của khách hàng |
| `cfs135` | Chi trả phí lưu ký chứng khoán của khách hàng |
| `cfs138` | Tiền thu của Tổ chức phát hành chứng khoán |
| `cfs139` | Tiền chi trả Tổ chức phát hành chứng khoán |
| `cfs140` | Lưu chuyển tiền hoạt động môi giới, ủy thác của khách hàng |
| `cfs141` | TIỀN VÀ CÁC KHOẢN TƯƠNG ĐƯƠNG TIỀN ĐẦU KỲ CỦA KHÁCH HÀNG |
| `cfs142` | Tiền gửi ngân hàng đầu kỳ |
| `cfs143` | Tiền gửi của NĐT về GDCK theo phương thức CTCK quản lý |
| `cfs144` | Trong đó: có kỳ hạn |
| `cfs145` | Tiền gửi tổng hợp GDCK cho khách hàng |
| `cfs147` | Tiền gửi của tổ chức phát hành |
| `cfs148` | Trong đó: có kỳ hạn |
| `cfs149` | Tiền gửi của NĐT về GDCK theo phương thức NHTM quản lý (Trước năm 2016) |
| `cfs152` | Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ |
| `cfs153` | TIỀN VÀ CÁC KHOẢN TƯƠNG ĐƯƠNG TIỀN CUỐI KỲ CỦA KHÁCH HÀNG |
| `cfs154` | Tiền gửi ngân hàng cuối kỳ |
| `cfs155` | Tiền gửi của NĐT về GDCK theo phương thức CTCK quản lý |
| `cfs156` | Trong đó: có kỳ hạn |
| `cfs159` | Tiền gửi tổng hợp GDCK cho khách hàng |
| `cfs160` | Tiền gửi bù trừ và thanh toán GDCK |
| `cfs161` | Tiền gửi của tổ chức phát hành |
| `cfs164` | Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ |
| `cfs165` | Điều chỉnh cho các khoản |
| `cfs167` | Tăng các chi phí phi tiền tệ |
| `cfs168` | Lỗ đánh giá giá trị các tài sản tài chính ghi nhận thông qua lãi/lỗ FVTPL |
| `cfs173` | Lỗ suy giảm giá trị các khoản đầu tư nắm giữ đến ngày đáo hạn (HTM) |
| `cfs174` | Lỗ suy giảm giá trị các khoản cho vay |
| `cfs175` | Lỗ về ghi nhận chênh lệch đánh giá theo giá trị hợp lý tài sản tài chính sẵn sàng để bán AFS khi phân loại lại |
| `cfs179` | Chi phí dự phòng suy giảm giá trị các khoản đầu tư tài chính dài hạn |
| `cfs181` | Lỗ khác |
| `cfs182` | Giảm các doanh thu phi tiền tệ |
| `cfs183` | Lãi đánh giá giá trị các tài sản chính ghi nhận thông qua lãi/lỗ FVTPL |
| `cfs187` | Lãi về ghi nhận chệnh lệch đánh giá theo giá trị hợp lý tài sản tài chính sẵn sàng để bán AFS khi phân loại lại |
| `cfs193` | Lãi khác |
| `cfs194` | Thay đổi tài sản và nợ phải trả hoạt động (Trước năm 2016) |
| `cfs195` | Tăng (giảm) tài sản tài chính ghi nhận thông qua lãi/ lỗ (FVTPL) |
| `cfs196` | Tăng (giảm) các khoản đầu tư giữ đến ngày đáo hạn (HTM) |
| `cfs197` | Tăng(giảm) các khoản cho vay |
| `cfs198` | Tăng (giảm) tài sản tài chính sẵn sàng để bán AFS |
| `cfs199` | Tăng/giảm các tài sản khác |
| `cfs200` | Tăng/giảm các khoản phải thu (Trước năm 2016) |
| `cfs201` | Tăng/giảm vay và nợ thuê tài sản tài chính (Trước năm 2016) |
| `cfs206` | (-) Tăng, (+) giảm phải thu bán các tài sản tài chính |
| `cfs207` | (-) Tăng, (+) giảm phải thu và dự thu cổ tức, tiền lãi các tài sản tài chính |
| `cfs208` | (-) Tăng, (+) giảm các khoản phải thu các dịch vụ CTCK cung cấp |
| `cfs209` | (-) Tăng, (+) giảm các khoản phải thu về lỗi giao dịch các TSTC |
| `cfs210` | (+) Tăng, (-) giảm phải trả cho người bán |
| `cfs212` | (+) Tăng, (-) giảm các khoản trích nộp phúc lợi nhân viên |
| `cfs213` | (+) Tăng, (-) giảm thuế và các khoản phải nộp Nhà nước |
| `cfs214` | (+) Tăng, (-) giảm phải trả người lao động |
| `cfs216` | Tiền lãi đã thu |
| `cfs217` | Tiền thu khác |
| `cfs218` | cfs218 |
| `cfs220` | Các khoản chi khác |
| `cfs222` | cfs222 |
| `cfs223` | (-) Tăng, (+) giảm chi phí phải trả (không bao gồm chi phí lãi vay) |
| `cfs224` | Chi trả thanh toán giao dịch chứng khoán của khách hàng |
| `cfs225` | Chi trả cho hoạt động ủy thác đầu tư của khách hàng |
| `cfs84` | cfs84 |

Shared identifier columns: `ticker`, `period_kind`, `year`, `quarter`, `period_months`, `public_date`.

## Balance Sheet.csv

All financial data columns use the original Vietcap field code exactly. The table below maps each code to its display label.

| Vietcap field code / CSV column | Display label |
| --- | --- |
| `bsa1` | TÀI SẢN NGẮN HẠN |
| `bsa10` | Trả trước người bán |
| `bsa11` | Phải thu nội bộ |
| `bsa12` | Phải thu hợp đồng xây dựng đang thực hiện |
| `bsa13` | Phải thu khác |
| `bsa14` | Dự phòng nợ khó đòi |
| `bsa15` | Hàng tồn kho, ròng |
| `bsa159` | Phải thu cho vay ngắn hạn |
| `bsa16` | Hàng tồn kho |
| `bsa160` | Giao dịch mua bán lại trái phiếu Chính phủ |
| `bsa161` | Trả trước người bán dài hạn |
| `bsa162` | Phải thu cho vay dài hạn |
| `bsa163` | Tài sản dở dang dài hạn |
| `bsa164` | Chi phí sản xuất, kinh doanh dở dang dài hạn |
| `bsa165` | Đầu tư nắm giữ đến ngày đáo hạn |
| `bsa166` | Thiết bị, vật tư, phụ tùng thay thế dài hạn |
| `bsa167` | Doanh thu chưa thực hiện ngắn hạn |
| `bsa168` | Quỹ bình ổn giá |
| `bsa169` | Giao dịch mua bán lại trái phiếu chính phủ |
| `bsa17` | Dự phòng giảm giá hàng tồn kho |
| `bsa170` | Người mua trả tiền trước dài hạn |
| `bsa171` | Chi phí phải trả dài hạn |
| `bsa173` | Trái phiếu chuyển đổi |
| `bsa174` | Cổ phiếu ưu đãi |
| `bsa175` | Cổ phiếu phổ thông |
| `bsa176` | Quyền chọn chuyển đổi trái phiếu |
| `bsa177` | LNST chưa phân phối lũy kế đến cuối kỳ trước |
| `bsa178` | LNST chưa phân phối kỳ này |
| `bsa18` | Tài sản lưu động khác |
| `bsa188` | Xây dựng cơ bản đang dở dang |
| `bsa19` | Chi phí trả trước ngắn hạn |
| `bsa2` | Tiền và tương đương tiền |
| `bsa20` | Thuế GTGT được khấu trừ |
| `bsa209` | Lợi thế thương mại |
| `bsa21` | Phải thu thuế khác |
| `bsa210` | Lợi ích cổ đông không kiểm soát |
| `bsa211` | Nguồn kinh phí đã hình thành TSCĐ |
| `bsa22` | Tài sản lưu động khác |
| `bsa23` | TÀI SẢN DÀI HẠN |
| `bsa24` | Phải thu dài hạn |
| `bsa25` | Phải thu khách hàng dài hạn |
| `bsa26` | Phải thu nội bộ dài hạn |
| `bsa27` | Phải thu dài hạn khác |
| `bsa276` | Vốn Góp liên doanh |
| `bsa277` | Đầu tư vào công ty liên kết |
| `bsa278` | bsa278 |
| `bsa28` | Dự phòng phải thu dài hạn |
| `bsa29` | Tài sản cố định |
| `bsa3` | Tiền |
| `bsa30` | GTCL TSCĐ hữu hình |
| `bsa31` | Nguyên giá TSCĐ hữu hình |
| `bsa32` | Khấu hao lũy kế TSCĐ hữu hình |
| `bsa33` | GTCL tài sản thuê tài chính |
| `bsa34` | Nguyên giá tài sản thuê tài chính |
| `bsa35` | Khấu hao lũy kế tài sản thuê tài chính |
| `bsa36` | GTCL tài sản cố định vô hình |
| `bsa37` | Nguyên giá TSCĐ vô hình |
| `bsa38` | Khấu hao lũy kế TSCĐ vô hình |
| `bsa39` | Xây dựng cơ bản đang dang dở (trước 2015) |
| `bsa4` | Các khoản tương đương tiền |
| `bsa40` | Giá trị ròng tài sản đầu tư |
| `bsa41` | Nguyên giá tài sản đầu tư |
| `bsa42` | Khấu hao lũy kế tài sản đầu tư |
| `bsa43` | Đầu tư dài hạn |
| `bsa44` | Đầu tư vào các công ty con |
| `bsa45` | Đầu tư vào các công ty liên kết |
| `bsa46` | Đầu tư dài hạn khác |
| `bsa47` | Dự phòng giảm giá đầu tư dài hạn |
| `bsa48` | Lợi thế thương mại (trước 2015) |
| `bsa49` | Tài sản dài hạn khác |
| `bsa5` | Đầu tư ngắn hạn |
| `bsa50` | Trả trước dài hạn |
| `bsa51` | Thuế thu nhập hoãn lại |
| `bsa52` | Các tài sản dài hạn khác |
| `bsa53` | TỔNG CỘNG TÀI SẢN |
| `bsa54` | NỢ PHẢI TRẢ |
| `bsa55` | Nợ ngắn hạn |
| `bsa56` | Vay ngắn hạn |
| `bsa57` | Phải trả người bán |
| `bsa58` | Người mua trả tiền trước |
| `bsa59` | Thuế và các khoản phải trả Nhà nước |
| `bsa6` | Đầu tư ngắn hạn |
| `bsa60` | Phải trả người lao động |
| `bsa61` | Chi phí phải trả |
| `bsa62` | Phải trả nội bộ |
| `bsa63` | Phải trả về xây dựng cơ bản |
| `bsa64` | Phải trả khác |
| `bsa65` | Dự phòng các khoản phải trả ngắn hạn |
| `bsa66` | Quỹ khen thưởng, phúc lợi |
| `bsa67` | Nợ dài hạn |
| `bsa68` | Phải trả nhà cung cấp dài hạn |
| `bsa69` | Phải trả nội bộ dài hạn |
| `bsa7` | Dự phòng giảm giá |
| `bsa70` | Phải trả dài hạn khác |
| `bsa71` | Vay dài hạn |
| `bsa72` | Thuế thu nhập hoãn lại |
| `bsa73` | Dự phòng trợ cấp thôi việc |
| `bsa74` | Dự phòng các khoản nợ dài hạn |
| `bsa75` | bsa75 |
| `bsa76` | Doanh thu chưa thực hiện |
| `bsa77` | Quỹ phát triển khoa học công nghệ |
| `bsa78` | Vốn chủ sở hữu |
| `bsa79` | Vốn và các quỹ |
| `bsa8` | Các khoản phải thu |
| `bsa80` | Vốn góp |
| `bsa81` | Thặng dư vốn cổ phần |
| `bsa82` | Vốn khác |
| `bsa83` | Cổ phiếu quỹ |
| `bsa84` | Chênh lệch đánh giá lại tài sản |
| `bsa85` | Chênh lệch tỷ giá |
| `bsa86` | Quỹ đầu tư và phát triển |
| `bsa87` | Quỹ dự phòng tài chính |
| `bsa88` | Quỹ dự trữ bắt buộc |
| `bsa89` | Quỹ khác |
| `bsa9` | Phải thu khách hàng |
| `bsa90` | Lãi chưa phân phối |
| `bsa91` | Quỹ hỗ trợ sắp xếp doanh nghiệp |
| `bsa92` | Vốn Ngân sách nhà nước và quỹ khác |
| `bsa94` | Vốn ngân sách nhà nước và quỹ khác |
| `bsa95` | Lợi ích của cổ đông thiểu số |
| `bsa96` | Tổng cộng nguồn vốn |
| `bsb100` | Chứng khoán kinh doanh |
| `bsb101` | Dự phòng giảm giá chứng khoán kinh doanh |
| `bsb102` | Các công cụ tài chính phái sinh và các tài sản tài chính khác |
| `bsb103` | Cho vay khách hàng |
| `bsb104` | Cho vay khách hàng |
| `bsb105` | Dự phòng rủi ro cho vay khách hàng |
| `bsb106` | Chứng khoán đầu tư |
| `bsb107` | Chứng khoán đầu tư sẵn sàng để bán |
| `bsb108` | Đầu tư nắm giữ đến ngày đáo hạn |
| `bsb109` | Dự phòng giảm giá chứng khoán đầu tư |
| `bsb110` | Tài sản Có khác |
| `bsb111` | Các khoản nợ chính phủ và NHNN Việt Nam |
| `bsb112` | Tiền gửi và vay các Tổ chức tín dụng khác |
| `bsb113` | Tiền gửi của khách hàng |
| `bsb114` | Các công cụ tài chính phái sinh và các khoản nợ tài chính khác |
| `bsb115` | Vốn tài trợ, uỷ thác đầu tư của Chính phủ và các tổ chức tín dụng khác |
| `bsb116` | Phát hành giấy tờ có giá |
| `bsb117` | Các khoản nợ khác |
| `bsb118` | Vốn của tổ chức tín dụng |
| `bsb119` | Vốn đầu tư XDCB |
| `bsb120` | Cổ phiếu ưu đãi |
| `bsb121` | Quỹ của tổ chức tín dụng |
| `bsb122` | bsb122 |
| `bsb125` | bsb125 |
| `bsb126` | bsb126 |
| `bsb131` | Bảo lãnh khác |
| `bsb132` | bsb132 |
| `bsb157` | bsb157 |
| `bsb158` | Cam kết giao dịch hối đoái |
| `bsb179` | bsb179 |
| `bsb180` | Cam kết mua ngoại tệ |
| `bsb181` | Cam kết bán ngoại tệ |
| `bsb182` | Cam kết giao dịch hoán đổi |
| `bsb184` | Cam kết cho vay không hủy ngang |
| `bsb185` | Cam kết trong nghiệp vụ L/C |
| `bsb186` | Cam kết khác |
| `bsb258` | Tiền gửi tại các TCTD khác |
| `bsb259` | Cho vay các TCTD khác |
| `bsb260` | Dự phòng rủi ro |
| `bsb261` | Hoạt động mua nợ |
| `bsb262` | Mua nợ |
| `bsb263` | Dự phòng rủi ro hoạt động mua nợ |
| `bsb264` | Các khoản phải thu |
| `bsb265` | Các khoản lãi và phí phải thu |
| `bsb266` | Tài sản thuế TNDN hoãn lại |
| `bsb267` | Tài sản Có khác |
| `bsb268` | Trong đó: Lợi thế thương mại |
| `bsb269` | Các khoản dự phòng rủi ro cho các tài sản Có nội bảng khác |
| `bsb270` | Tiền gửi của các tổ chức tín dụng khác |
| `bsb271` | Vay các tổ chức tín dụng khác |
| `bsb272` | Các khoản lãi, phí phải trả |
| `bsb273` | Thuế TNDN hoãn lại phải trả |
| `bsb274` | Các khoản phải trả và công nợ khác |
| `bsb275` | Dự phòng rủi ro khác |
| `bsb97` | Tiền gửi tại Ngân hàng nhà nước Việt Nam |
| `bsb98` | Tiền gửi tại các TCTD khác và cho vay các TCTD khác |
| `bsb99` | Chứng khoán kinh doanh |
| `bsi141` | Tài sản thiếu cần xử lý |
| `bsi151` | bsi151 |
| `bsi152` | bsi152 |
| `bsi153` | bsi153 |
| `bsi154` | bsi154 |
| `bsi155` | bsi155 |
| `bsi156` | bsi156 |
| `bsi190` | Chi phí hoa hồng chưa phân bổ |
| `bsi191` | Chi phí trả trước ngắn hạn khác |
| `bsi192` | Tài sản tái bảo hiểm |
| `bsi193` | Dự phòng phí nhượng tái bảo hiểm |
| `bsi194` | Dự phòng bồi thường nhượng tái bảo hiểm |
| `bsi195` | Ký quỹ bảo hiểm |
| `bsi196` | Phải thu dài hạn khác |
| `bsi197` | Doanh thu hoa hồng chưa được hưởng |
| `bsi198` | Phải thu về hợp đồng bảo hiểm |
| `bsi199` | Phải thu khác của khách hàng |
| `bsi200` | Phải trả về hợp đồng bảo hiểm |
| `bsi201` | Phải trả cho người bán |
| `bsi202` | Dự phòng nghiệp vụ bảo hiểm |
| `bsi203` | Dự phòng phí chưa được hưởng |
| `bsi204` | Dự phòng toán học |
| `bsi205` | Dự phòng bồi thường |
| `bsi206` | Dự phòng dao động lớn |
| `bsi207` | Dự phòng chia lãi |
| `bsi208` | Dự phòng đảm bảo cân đối |
| `bsi281` | bsi281 |
| `bsi282` | bsi282 |
| `bsi283` | bsi283 |
| `bsi284` | bsi284 |
| `bsi285` | bsi285 |
| `bsi287` | bsi287 |
| `bss134` | Vốn kinh doanh ở các đơn vị trực thuộc |
| `bss135` | Phải trả hoạt động giao dịch chứng khoán |
| `bss136` | Phải trả cổ tức, gốc và lãi trái phiếu (Trước năm 2016) |
| `bss138` | Quỹ bảo vệ Nhà đầu tư |
| `bss189` | bss189 |
| `bss212` | Tiền chi nộp Quỹ Hỗ trợ thanh toán |
| `bss214` | Tài sản tài chính ngắn hạn |
| `bss215` | Các khoản cho vay |
| `bss216` | Các khoản tài chính sẵn sàng để bán (AFS) |
| `bss217` | Các khoản phải thu (từ 2016) |
| `bss218` | Phải thu bán các tài sản tài chính |
| `bss219` | Phải thu và dự thu cổ tức, tiền lãi các tài sản tài chính |
| `bss220` | Phải thu cổ tức, tiền lãi đến ngày nhận |
| `bss222` | Dự thu cổ tức , tiền lãi chưa đến ngày nhận |
| `bss224` | Phải thu các dịch vụ CTCK cung cấp |
| `bss226` | Dự phòng suy giảm giá trị các khoản phải thu |
| `bss227` | Tạm ứng |
| `bss228` | Vật tư văn phòng, công cụ, dụng cụ |
| `bss229` | Cầm cố, thế chấp, ký quý , ký cược ngắn hạn |
| `bss230` | Dự phòng suy giảm giá trị TSNH khác |
| `bss231` | Tài sản tài chính dài hạn |
| `bss236` | Cầm cố, thế chấp, kỹ quỹ, Ký cược dài hạn |
| `bss238` | Vay ngắn hạn |
| `bss239` | Nợ thuê tài sản tài chính ngắn hạn |
| `bss241` | Trái phiếu chuyển đổi ngắn hạn - Cấu phần nợ |
| `bss242` | Trái phiếu phát hành ngắn hạn |
| `bss245` | Các khoản trích nộp phúc lợi nhân viên |
| `bss246` | Nhận ký quỹ, ký cược ngắn hạn |
| `bss247` | Vay dài hạn |
| `bss248` | Nợ thuê tài chính dài hạn |
| `bss250` | Trái phiếu phát hành dài hạn |
| `bss251` | Nhận ký quỹ, ký cược dài hạn |
| `bss252` | Vốn đầu tư của chủ sở hữu |
| `bss253` | Quỹ dự trữ bổ sung vốn điều lệ |
| `bss254` | Lợi nhuận đã thực hiện |
| `bss255` | Lợi nhuận chưa thực hiện |
| `nos355` | Tài sản cố định thuê ngoài |
| `nos356` | Chứng chỉ có giá nhận giữ hộ |
| `nos357` | Tài sản nhận thế chấp |
| `nos358` | Nợ khó đòi đã xử lý |
| `nos359` | Ngoại tệ các loại |
| `nos360` | Cổ phiếu đang lưu hành (Số lượng) |
| `nos361` | Cổ phiếu quỹ (Số lượng) |
| `nos362` | Tài sản tài chính niêm yết/đăng ký giao dịch tại VSD của CTCK |
| `nos370` | Tài sản tài chính đã lưu ký tại VSD và chưa giao dịch của CTCK |
| `nos375` | Tài sản tài chính chờ về của CTCK |
| `nos377` | Tài sản tài chính chưa lưu ký tại VSD của CTCK |
| `nos378` | Tài sản tài chính được hưởng quyền của CTCK |
| `nos379` | Tài sản tài chính niêm yết/đăng ký giao dịch tại VSD của NĐT |
| `nos380` | Tài sản tài chính giao dịch tự do chuyển nhượng |
| `nos381` | Tài sản tài chính hạn chế chuyển nhượng |
| `nos382` | Tài sản tài chính giao dịch cầm cố |
| `nos383` | Tài sản tài chính phong tỏa, tạm giữ |
| `nos384` | Tài sản tài chính chờ thanh toán |
| `nos385` | Tài sản tài chính chờ cho vay |
| `nos386` | Tài sản tài chính đã lưu ký tại VSD và chưa giao dịch của NĐT |
| `nos387` | Tài sản tài chính đã lưu ký tại VSD và chưa giao dịch, tự do chuyển nhượng |
| `nos388` | Tài sản tài chính đã lưu ký tại VSD và chưa giao dịch, hạn chế chuyển nhượng |
| `nos389` | Tài sản tài chính đã lưu ký tại VSD và chưa giao dịch, cầm cố |
| `nos390` | Tài sản tài chính đã lưu ký tại VSD và chưa giao dịch, phong tỏa, tạm giữ |
| `nos391` | Tài sản tài chính chờ về của NĐT |
| `nos392` | Tài sản tài chính sửa lỗi giao dịch của NĐT |
| `nos393` | Tài sản tài chính chưa lưu ký tại VSD của NĐT |
| `nos394` | Tài sản tài chính được hưởng quyền của Nhà đầu tư |
| `nos395` | Tiền gửi của khách hàng |
| `nos396` | Tiền gửi của Nhà đầu tư về giao dịch chứng khoán |
| `nos399` | Tiền gửi tổng hợp giao dịch chứng khoán cho khách hàng |
| `nos410` | Phải trả Tổ chức phát hành chứng khoán |
| `nos411` | Phải thu/phải trả của khách hàng về lỗi giao dịch các tài sản tài chính |
| `nos413` | Phải trả cổ tức, gốc và lãi trái phiếu |
| `nos607` | Tiền gửi bù trừ và thanh toán giao dịch chứng khoán của NĐT |
| `nos608` | Tiền gửi bù trừ và thanh toán giao dịch chứng khoán của NĐT trong nước |
| `nos609` | Tiền gửi bù trừ và thanh toán giao dịch chứng khoán của NĐT nước ngoài |
| `nos610` | TIỀN GỬI CỦA TỔ CHỨC PHÁT HÀNH |
| `nos614` | Phải trả NĐT - Tiền gửi của NĐT về tiền gửi giao dịch CK theo phương thức CTCK quản lý |
| `nos615` | Của Nhà đầu tư trong nước |
| `nos616` | Của Nhà đầu tư nước ngoài |

Shared identifier columns: `ticker`, `period_kind`, `year`, `quarter`, `period_months`, `public_date`.

## Income Statement.csv

All financial data columns use the original Vietcap field code exactly. The table below maps each code to its display label.

| Vietcap field code / CSV column | Display label |
| --- | --- |
| `isa1` | Doanh thu bán hàng và cung cấp dịch vụ |
| `isa10` | Chi phí quản lý doanh nghiệp |
| `isa102` | Lãi/(lỗ) từ công ty liên doanh (từ năm 2015) |
| `isa11` | Lãi/(lỗ) từ hoạt động kinh doanh |
| `isa12` | Thu nhập khác |
| `isa13` | Chi phí khác |
| `isa14` | Thu nhập khác, ròng |
| `isa15` | Lãi/(lỗ) từ công ty liên doanh |
| `isa16` | Lãi/(lỗ) trước thuế |
| `isa17` | Thuế thu nhập doanh nghiệp - hiện thời |
| `isa18` | Thuế thu nhập doanh nghiệp - hoãn lại |
| `isa19` | Chi phí thuế thu nhập doanh nghiệp |
| `isa2` | Các khoản giảm trừ doanh thu |
| `isa20` | Lãi/(lỗ) thuần sau thuế |
| `isa21` | Lợi ích của cổ đông thiểu số |
| `isa22` | Lợi nhuận của Cổ đông của Công ty mẹ |
| `isa23` | Lãi cơ bản trên cổ phiếu (VND) |
| `isa24` | Lãi trên cổ phiếu pha loãng (VND) |
| `isa3` | Doanh thu thuần |
| `isa4` | Giá vốn hàng bán |
| `isa5` | Lợi nhuận gộp |
| `isa6` | Doanh thu hoạt động tài chính |
| `isa7` | Chi phí tài chính |
| `isa8` | Chi phí lãi vay |
| `isa9` | Chi phí bán hàng |
| `isb25` | Thu nhập lãi và các khoản thu nhập tương tự |
| `isb26` | Chi phí lãi và các chi phí tương tự |
| `isb27` | Thu nhập lãi thuần |
| `isb28` | Thu nhập từ dịch vụ |
| `isb29` | Chi phí dịch vụ |
| `isb30` | Lãi/Lỗ thuần từ hoạt động dịch vụ |
| `isb31` | Lãi/(lỗ) thuần từ hoạt động kinh doanh ngoại hối và vàng |
| `isb32` | Lãi/(lỗ) thuần từ mua bán chứng khoán kinh doanh |
| `isb33` | Lãi/(lỗ) thuần từ mua bán chứng khoán đầu tư |
| `isb34` | Thu nhập khác |
| `isb35` | Chi phí khác |
| `isb36` | Lợi nhuận hoạt động khác |
| `isb37` | Thu nhập từ cổ tức |
| `isb38` | Tổng thu nhập hoạt động |
| `isb39` | Chi phí quản lý doanh nghiệp |
| `isb40` | Lợi nhuận thuần hoạt động trước khi trích lập dự phòng tổn thất tín dụng |
| `isb41` | Trích lập dự phòng tổn thất tín dụng |
| `isi100` | Lợi nhuận hoạt động tài chính |
| `isi103` | Doanh thu từ phí bảo hiểm |
| `isi104` | Tăng/(giảm) dư phòng phí bảo hiểm chưa được hưởng |
| `isi105` | Doanh thu phí bảo hiểm thuần |
| `isi106` | Hoa hồng nhượng tái bảo hiểm và doanh thu khác HĐKD Bảo hiểm |
| `isi107` | Thu bồi thường từ nhượng tái bảo hiểm |
| `isi108` | Tăng/(giảm) dự phòng toán học |
| `isi109` | Tăng/(giảm) dự phòng bồi thường bảo hiểm gốc và nhận tái bảo hiểm |
| `isi110` | Tăng/(giảm) dự phòng bồi thường nhượng tái bảo hiểm |
| `isi111` | Tổng chi bồi thường bảo hiểm |
| `isi112` | Chi bán hàng |
| `isi114` | Lãi thuần từ hoạt động bảo hiểm phi nhân thọ |
| `isi175` | isi175 |
| `isi176` | isi176 |
| `isi177` | isi177 |
| `isi178` | Lợi nhuận từ hoạt động đầu tư bất động sản |
| `isi179` | Doanh thu từ kinh doanh bất động sản đầu tư |
| `isi180` | Giá vốn bất động sản đầu tư |
| `isi51` | Thu phí bảo hiểm gốc |
| `isi52` | Thu phí nhận tái bảo hiểm |
| `isi53` | Các khoản giảm trừ doanh thu |
| `isi54` | Phí nhượng tái bảo hiểm |
| `isi55` | Giảm phí |
| `isi56` | Hoàn phí |
| `isi59` | Thu hoa hồng nhượng tái bảo hiểm |
| `isi60` | Thu nhập khác |
| `isi63` | Thu hoạt động khác |
| `isi64` | Doanh thu thuần từ hoạt động kinh doanh bảo hiểm |
| `isi65` | Chi bồi thường bảo hiểm gốc và chi trả đáo hạn |
| `isi66` | Chi bồi thường nhận tái bảo hiểm |
| `isi67` | Các khoản giảm trừ chi phí |
| `isi69` | Thu đòi thứ ba |
| `isi70` | Thu xử lý hàng bồi thường 100% |
| `isi71` | Bồi thường thuộc trách nhiệm giữ lại |
| `isi72` | Chi bồi thường từ quỹ dao động lớn |
| `isi73` | Tăng/(giảm) dự phòng bồi thường |
| `isi74` | Trích dự phòng dao động lớn |
| `isi75` | Chi khác hoạt động kinh doanh bảo hiểm |
| `isi76` | Chi khác hoạt động bảo hiểm gốc |
| `isi77` | Chi hoa hồng bảo hiểm gốc |
| `isi82` | Chi khác |
| `isi83` | Chi khác nhận tái bảo hiểm |
| `isi84` | Chi nhượng tái bảo hiểm khác |
| `isi86` | Tổng chi trực tiếp hoạt động kinh doanh bảo hiểm |
| `isi87` | Lợi nhuận gộp hoạt động kinh doanh bảo hiểm |
| `isi91` | Thu nhập từ hoạt động khác |
| `isi92` | Chi phí từ hoạt động khác |
| `isi93` | Thu nhập thuần từ các hoạt động khác |
| `isi94` | Chi phí quản lý doanh nghiệp liên quan trực tiếp đến hoạt động bảo hiểm |
| `isi97` | Lợi nhuận thuần hoạt động kinh doanh bảo hiểm |
| `isi99` | Lãi thuần từ các hoạt động khác |
| `iss115` | Lãi từ các tài sản tài chính ghi nhận thông qua lãi/lỗ ( FVTPL) |
| `iss116` | Lãi bán các tài sản tài chính FVTPL |
| `iss117` | Chênh lệch tăng đánh giá lại các TSTC thông qua lãi/lỗ |
| `iss118` | Cổ tức, tiền lãi phát sinh từ tài sản tài chính FVTPL |
| `iss119` | Lãi từ các khoản đầu tư nắm giữ đến ngày đáo hạn |
| `iss120` | Lãi từ các khoản cho vay và phải thu |
| `iss121` | Lãi từ các tài sản tài chính sẵn sàng để bán |
| `iss122` | Lãi từ các công cụ phát sinh phòng ngừa rủi ro |
| `iss123` | Doanh thu hoạt động tư vấn tài chính |
| `iss124` | Lỗ các tài sản tài chính ghi nhận thông qua lãi lỗ (FVTPL) |
| `iss125` | Lỗ bán các tài sản tài chính |
| `iss126` | Chênh lệch giảm đánh giá lại các TSTC thông qua lãi/lỗ |
| `iss127` | Chi phí giao dịch mua các tài sản tài chính FVTPL |
| `iss128` | Lỗ các khoản đầu tư nắm giữ đến ngày đáo hạn (HTM) |
| `iss130` | Lỗ và ghi nhận chênh lệch đánh giá theo giá trị hợp lý tài sản tài chính sẵn sàng để bán (AFS) khi phân loại lại |
| `iss132` | Chi phí hoạt động tự doanh |
| `iss133` | Chi phí nghiệp vụ môi giới chứng khoán |
| `iss134` | Chi phí nghiệp vụ bảo lãnh, đại lý phát hành chứng khoán |
| `iss135` | Chi phí nghiệp vụ tư vấn đầu tư chứng khoán |
| `iss137` | Chi phí nghiệp vụ lưu ký chứng khoán |
| `iss138` | Chi phí hoạt động tư vấn tài chính |
| `iss139` | Chi phí các dịch vụ khác |
| `iss141` | DOANH THU HOẠT ĐỘNG TÀI CHÍNH |
| `iss142` | Chênh lệch lãi tỷ giá hối đoái đã và chưa thực hiện |
| `iss143` | Doanh thu, dự thu cổ tức, lãi tiền gửi không cố định phát sinh trong kỳ |
| `iss144` | Lãi bán, thanh lý các khoản đầu tư vào công ty con, liên kết, liên doanh |
| `iss145` | Doanh thu khác về đầu tư |
| `iss146` | CHI PHÍ TÀI CHÍNH |
| `iss147` | Chênh lệch lỗ tỷ giá hối đoái đã và chưa thực hiện |
| `iss148` | Chi phí lãi vay |
| `iss149` | Lỗ bán, thanh lý các khoản đầu tư vào công ty con, liên kết, liên doanh |
| `iss150` | Chi phí dự phòng suy giảm giá trị các khoản đầu tư tài chính dài hạn |
| `iss151` | Chi phí đầu tư khác |
| `iss152` | CHI PHÍ BÁN HÀNG |
| `iss153` | Lợi nhuận đã thực hiện |
| `iss154` | Lợi nhuận chưa thực hiện |
| `iss155` | LNST trích các Quỹ dự trữ điều lệ, Quỹ Dự phòng tài chính và rủi ro nghề nghiệp |
| `iss157` | Lãi/(lỗ) từ đánh giá lại các tài sản tài chính sẵn sàng để bán |
| `iss158` | Lãi/(lỗ) toàn diện khác được chia từ hoạt động đầu tư vào công ty con, đầu tư liên kết, liên doanh |
| `iss160` | Lãi/(lỗ) chênh lệch tỷ giá của hoạt động tại nước ngoài |
| `iss164` | Tổng thu nhập toàn diện |
| `iss165` | Thu nhập toàn diện phân bổ cho chủ sở hữu |
| `iss166` | Thu nhập toàn diện phân bổ cho cổ đông không nắm quyền kiểm soát |
| `iss167` | THU NHẬP THUẦN TRÊN CỔ PHIẾU PHỔ THÔNG |
| `iss168` | CP dự phòng TSTC, xử lý tổn thất các khoản phải thu khó đòi là lỗ suy giảm TSTC và CP đi vay |
| `iss174` | THU NHẬP (LỖ) TOÀN DIỆN KHÁC SAU THUẾ |
| `iss42` | Doanh thu nghiệp vụ môi giới chứng khoán |
| `iss44` | Doanh thu nghiệp vụ bảo lãnh phát hành chứng khoán |
| `iss45` | iss45 |
| `iss46` | Doanh thu nghiệp vụ tư vấn đầu tư chứng khoán |
| `iss47` | Doanh thu lưu ký chứng khoán |
| `iss50` | Doanh thu khác |
| `cfa2` | Khấu hao TSCĐ và BĐSĐT |

Shared identifier columns: `ticker`, `period_kind`, `year`, `quarter`, `period_months`, `public_date`.
