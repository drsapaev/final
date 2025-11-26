#  A?@02;5=85 QR G5@548 -  57N<5

## @>1;5<0

@8 A:0=8@>20=88 QR :>4>2 =0 B5;5D>=5:
-  0@48>;>3 - @01>B0;
- L 5@<0B>;>3 - "G5@54L =5 0:B82=0"
-  !B><0B>;>3 - @01>B0;
- L 01>@0B>@8O - "G5@54L =5 0:B82=0"

## 0945==0O ?@8G8=0

**@>1;5<0 1K;0  2 :>=:@5B=KE A?5F80;8AB0E!**

 <5B>45 `complete_join_session()` (AB@>:0 409) 8A?>;L7>20;0AL **A53>4=OH=OO 40B0** (`date.today()`), 0 QR :>4K 1K;8 A>740=K =0 **702B@0** (2025-11-06).

### > 8A?@02;5=8O:
```python
today = date.today()  # L 2025-11-05
daily_queue = self.db.query(DailyQueue).filter(
    DailyQueue.day == today,  # I5B >G5@54L =0 2025-11-05
    ...
)
```

### >A;5 8A?@02;5=8O:
```python
target_date = qr_token.day  #  2025-11-06 (87 B>:5=0)
daily_queue = self.db.query(DailyQueue).filter(
    DailyQueue.day == target_date,  # I5B >G5@54L =0 ?@028;L=CN 40BC
    ...
)
```

## 'B> 1K;> 8A?@02;5=>

**$09;:** `backend/app/services/qr_queue_service.py` (AB@>:8 408-423)

>102;5=>:
- A?>;L7C5BAO `qr_token.day` 2<5AB> `date.today()`
- >102;5=> ;>38@>20=85 4;O 4803=>AB8:8
- @>25@:0 =0945==>9 DailyQueue

##  57C;LB0B

<‰ **"5?5@L ! 4 A?5F80;8AB0 @01>B0NB :>@@5:B=>!**

-  0@48>;>3
-  5@<0B>;>3
-  !B><0B>;>3
-  01>@0B>@8O

## 0: ?@>B5AB8@>20BL

1. #1548B5AL, GB> backend 70?CI5=:
   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. B:@>9B5 =0 B5;5D>=5 ;N1CN 87 AAK;>::
   - 0@48>;>3: `http://192.168.1.9:5173/queue/join?token=IST-I7lkefF5eZ3b0vpM4tADCq7eLwYNj7J4lV9q4EA`
   - 5@<0B>;>3: `http://192.168.1.9:5173/queue/join?token=ysq1wWkuiViQWfB8E5WBA5US8eErgg4QjsBheGjLenc`
   - !B><0B>;>3: `http://192.168.1.9:5173/queue/join?token=GqqHcPt02Th5LPK3anU4egvO5dJa8jaVdaqS2KvO41I`
   - 01>@0B>@8O: `http://192.168.1.9:5173/queue/join?token=AZFNLHtutd5IufVQx9kxhMMLSen0vEpNBac0077cPV0`

3. 0?>;=8B5 D>@<C:
   - $ (<8=8<C< 2 A8<2>;0)
   - "5;5D>= (<8=8<C< 5 A8<2>;>2, =0?@8<5@: +998928665369)
   - Telegram ID (>?F8>=0;L=>)

4. 06<8B5 "@>4>;68BL"

5. >;6=0 ?>O28BLAO AB@0=8F0 A =><5@>< 2 >G5@548 

## >G5<C @0=LH5 :070;>AL, GB> ?@>1;5<0 B>;L:> A 45@<0B>;>3>< 8 ;01>@0B>@859?

5@>OB=K9 ?>@O4>: B5AB8@>20=8O:
1. 0@48>;>3 (?5@2K9) ’   01>B0;
2. 5@<0B>;>3 ’ L 5 @01>B0;
3. **5@570?CA: backend**
4. !B><0B>;>3 (A=>20 ?5@2K9) ’   01>B0;
5. 01>@0B>@8O ’ L 5 @01>B0;

0 A0<>< 45;5 ?@>1;5<0 1K;0 **4;O 2A5E QR :>4>2 =0 702B@0H=NN 40BC**, =57028A8<> >B A?5F80;8AB0.

## >?>;=8B5;L=K5 8A?@02;5=8O

1.  8=0<8G5A:89 IP 4;O QR :>4>2
2.  Frontend 8A?>;L7C5B QR >B backend
3.  !:0G820=85 QR :0: PNG
4.  070 40==KE >1=>2;5=0 (visit_type, discount_mode, services)
5.  !5;5:B>@K 40BK 8 A?5F80;8AB0
6.  54C?;8:0F8O A?5F80;8AB>2
7.  **A?@02;5=0 ?@>1;5<0 A 40B0<8 2 complete_join_session**

## >;=0O 4>:C<5=B0F8O

- [QR_QUEUE_FINAL_STATUS.md](./QR_QUEUE_FINAL_STATUS.md) - >;=K9 AB0BCA ?@>5:B0
- [QR_QUEUE_BACKEND_HANG_DIAGNOSIS.md](./docs/QR_QUEUE_BACKEND_HANG_DIAGNOSIS.md) - 803=>AB8:0 (CAB0@5;0, backend =5 7028A0;)

## B>3

@>1;5<0 ?>;=>ABLN @5H5=0! !8AB5<0 QR >G5@5459 B5?5@L @01>B05B :>@@5:B=> 4;O 2A5E A?5F80;8AB>2 8 2A5E 40B.
