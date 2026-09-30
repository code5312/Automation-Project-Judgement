/* Curated scenarios, not production records. Patent excerpts are verified public text. */
window.LAB = {
  topics: [
    {id:'b1',n:'01',name:'반복 예외',role:'쇼핑몰 운영자',problem:'같은 상품코드 누락을 매번 찾아 고칩니다.',goal:'해결 경험을 규칙으로 만들어도 되는지 시험하세요.',steps:['사건 묶기','과거 재시험','범위 승인','새 주문 처리'],system:'비슷한 사건과 해결 이력을 묶고 적용 조건을 제안합니다.',human:'상품이 정말 같은지와 자동 적용 범위를 승인합니다.',data:'실패 주문·상품 속성·해결 행동·처리 결과',source:'https://support.atlassian.com/jira-service-management-cloud/docs/what-is-the-itil-problem-management-process/',sourceName:'Jira · 문제와 해결 이력 연결',guide:'먼저 반복 패턴을 찾고 과거 사례에 재시험하세요. 충돌 상품을 제외하는 조건을 고른 뒤 승인하면 새 주문을 처리할 수 있습니다. 비슷한 이름만으로 다른 상품을 합치지 않는 것이 핵심입니다.'},
    {id:'b2',n:'02',name:'자동화 충돌',role:'CRM 운영자',problem:'새 자동화가 기존 고객 상태를 덮어씁니다.',goal:'실행 순서를 바꾸고 충돌을 해결해 보세요.',steps:['흐름 비교','순서별 실행','수정 선택','재시험'],system:'같은 데이터를 쓰는 흐름을 찾고 실행 순서별 결과를 보여줍니다.',human:'업무 의도에 맞는 수정 방법과 배포 여부를 결정합니다.',data:'자동화 정의·공유 필드·시험 입력·실행 결과',source:'https://docs.n8n.io/workflows/executions/all-executions/',sourceName:'n8n · 실행 데이터 재사용과 재시도',guide:'두 실행 순서를 시험해 최종 고객 상태를 비교하세요. CS 상태를 별도 필드에 기록하도록 수정하면 두 업무의 정보를 모두 보존합니다. 고객이 여전히 관심 고객인지와 CS가 처리됐는지는 서로 다른 상태입니다.'},
    {id:'b3',n:'03',name:'변경 완료',role:'쇼핑몰 서비스 운영자',problem:'무료배송 정책을 바꿨는데 안내와 설정이 다릅니다.',goal:'변경을 반영하고 빠진 자료를 찾아 완료를 확인하세요.',steps:['프로젝트 탐색','영향 확정','변경 반영','누락 보정'],system:'연결된 자료를 제안하고 변경 후 값과 경계값 검증을 확인합니다.',human:'영향 범위를 확정하고 누락을 추가하며 완료를 승인합니다.',data:'정책·FAQ·상담 문구·설정·테스트·연결 관계',source:'https://learn.microsoft.com/en-us/azure/devops/pipelines/test/requirements-traceability?view=azure-devops',sourceName:'Azure DevOps · 요구사항·코드·테스트 추적',guide:'프로젝트 트리에서 자료를 살펴보고 변경 요청을 해석하세요. 영향 후보를 확정해 반영한 뒤 검사합니다. 상담 문구를 추가하면 보정할 수 있습니다. 5만원 주문 테스트는 여전히 유효하지만 새 경계값 3만원과 29,999원 검증이 필요합니다.'},
    {id:'d',n:'04',name:'IP 사건 탐지',role:'센서 제품 R&D 담당자',problem:'SDK 공개가 과거 비공개 판단의 전제를 바꿉니다.',goal:'검토를 요청하고 상황 변화에 다시 판단해 보세요.',steps:['공개 사건','과거 판단 연결','검토 기록','전제 재확인'],system:'공개 사건과 과거 결정을 연결하고 검토 신호·누락 정보를 정리합니다.',human:'검토 요청·정보 보류·공개 범위를 결정하고 이유와 전제를 남깁니다.',data:'공개 일정·개발 변경·과거 IP 결정·판단 전제',source:'https://www.wipo.int/en/web/patents/faq_patents',sourceName:'WIPO · 공개 전 검토의 중요성',guide:'SDK 이동 제안과 과거 비공개 판단을 확인하세요. 정보 부족 항목에는 준비된 예시 답변을 확인합니다. 공개 범위를 서버 내부 유지 또는 SDK 바이너리 포함으로 선택하고 본인 표현으로 전제를 기록하세요. 후속 릴리스에서 서버→SDK 또는 바이너리→원문 공개로 범위가 넓어지면 재검토 카드를 보여줍니다. 이 흐름은 시뮬레이션이며 출원·침해 여부를 판정하지 않습니다.'},
    {id:'patent',n:'05',name:'특허 검색 보조',role:'센서 제품 기술 담당자',problem:'검색된 문헌의 어떤 내용이 우리 기술과 연결되는지 읽어야 합니다.',goal:'실제 공개 문헌의 근거를 비교하고 검토 대상을 정하세요.',steps:['기술 설명','후보 탐색','근거 비교','판단 기록'],system:'준비된 공개 문헌에서 검색 조건에 맞는 후보와 비교할 근거를 보여줍니다.',human:'기술적 연결과 차이를 읽고 검토 대상·제외 이유를 기록합니다.',data:'기술 설명·검색 조건·공개 문헌·원문 근거·검토 이유',source:'https://www.wipo.int/edocs/pubdocs/en/wipo-pub-rn2021-1e-en-wipo-guide-to-using-patent-information.pdf',sourceName:'WIPO · 특허정보 활용',guide:'기술 설명의 압축·샘플링 조건을 바꾸어 후보를 탐색하세요. 후보를 선택하면 실제 원문 발췌와 비교 질문이 보입니다. 범위 확대 후 전력 절감 문헌을 추가할 수 있습니다. 이 화면은 준비된 3건을 필터링하며 KIPRIS 실시간 검색이나 유사도 순위를 표시하지 않습니다.'}
  ],
  orders:[
    {id:'O-1041',channel:'스마트스토어',external:'MUG-WHT',name:'데일리 머그 화이트',volume:350,target:'SKU-MUG-350-W',outcome:'정상 출고'},
    {id:'O-1058',channel:'스마트스토어',external:'MUG-WHT',name:'데일리 머그 흰색',volume:350,target:'SKU-MUG-350-W',outcome:'정상 출고'},
    {id:'O-1092',channel:'스마트스토어',external:'MUG-WHT',name:'데일리 머그 화이트',volume:500,target:'SKU-MUG-500-W',outcome:'수동 확인 후 정상 출고'},
    {id:'O-1103',channel:'자사몰',external:'MUG-WHT',name:'데일리 머그 화이트',volume:350,target:'SKU-SET-350-W',outcome:'세트 상품으로 별도 처리'}
  ],
  artifacts:[
    {id:'policy',group:'정책',name:'일반 고객 배송 정책',before:'일반 고객은 주문 금액 5만원 이상이면 무료배송입니다.',after:'일반 고객은 주문 금액 3만원 이상이면 무료배송입니다.',why:'변경 요청의 기준 문서',candidate:true,affected:true},
    {id:'faq',group:'고객 안내',name:'배송 FAQ',before:'오만 원 이상 주문하면 배송비를 받지 않습니다.',after:'삼만 원 이상 주문하면 배송비를 받지 않습니다.',why:'배송 정책을 고객 표현으로 설명',candidate:true,affected:true},
    {id:'cs',group:'고객 안내',name:'상담 답변 템플릿',before:'고객님, 배송비 면제는 결제 합계가 오만 원일 때부터 적용됩니다.',after:'고객님, 배송비 면제는 결제 합계가 삼만 원일 때부터 적용됩니다.',why:'검색 후보에서 빠진 동의 표현 · 사람이 추가 가능',candidate:false,affected:true},
    {id:'config',group:'서비스 설정',name:'배송비 계산 설정',before:'free_shipping_min_krw = 50000',after:'free_shipping_min_krw = 30000',why:'실제 배송비 계산에 쓰는 최소 금액',candidate:true,affected:true},
    {id:'tests',group:'품질 확인',name:'배송비 경계값 테스트',before:'50,000원 주문 → 배송비 0원 (기존 테스트 통과)',after:'29,999원 → 3,000원 / 30,000원 → 0원 / 50,000원 → 0원 (3건 통과)',why:'기존 테스트를 보존하고 새 기준 경계값을 추가',candidate:true,affected:true},
    {id:'vip',group:'정책',name:'VIP 배송 혜택',before:'VIP 고객은 주문 금액과 무관하게 무료배송입니다.',after:'VIP 고객은 주문 금액과 무관하게 무료배송입니다.',why:'일반 고객 금액 기준과 독립된 혜택',candidate:false,affected:false},
    {id:'payment',group:'서비스 설정',name:'간편결제 한도',before:'max_payment_krw = 50000',after:'max_payment_krw = 50000',why:'같은 숫자가 있어도 배송 정책과 무관',candidate:false,affected:false}
  ],
  events:[
    {id:'sdk',title:'압축 모듈의 SDK 이동 제안',text:'서버 내부 압축 모듈을 SDK에 넣자는 제안이 올라왔습니다. 아직 반영되지 않았고 공개 범위를 결정해야 합니다.',prior:'2026/03 · 영업비밀 유지',premise:'압축 구현은 서버에만 있고 외부에 배포되지 않는다.',signal:'과거 판단 전제 변화',kind:'review'},
    {id:'sampling',title:'새 적응형 샘플링 기능',text:'통신 상태에 따라 센서 데이터 수집 간격을 조정하는 기능이 SDK 릴리스에 추가됩니다.',prior:'연결된 검토 기록 없음',premise:'',signal:'미검토 기술 변경',kind:'review'},
    {id:'buffer',title:'버퍼 처리 개선',text:'변경 기록에는 성능 개선만 기재되어 구현 공개 범위를 알 수 없습니다.',prior:'연결된 검토 기록 없음',premise:'',signal:'추가 정보 필요',kind:'hold'},
    {id:'ui',title:'설정 화면 간격 변경',text:'센서 설정 화면의 여백만 조정했습니다. 처리 로직은 동일합니다.',prior:'화면 변경 기록 확인',premise:'',signal:'기술 구현 변경 없음',kind:'skip'}
  ],
  patents:[
    {id:'US9986069B2',title:'Devices and methods to compress sensor data',summary:'웨어러블 센서의 데이터를 통신 품질에 맞춰 압축하는 장치와 방법.',tags:['compression','sampling'],section:'청구항 1 · 일부 발췌',quote:'receive the detected link quality;',interpretation:'수신한 통신 품질에 따라 ADPCM 압축을 적용하는 구성을 청구항 1에서 다룹니다.',question:'우리 방식도 통신 품질을 입력으로 쓰나요? 압축 알고리즘과 초기화 조건은 어떻게 다른가요?',url:'https://patents.google.com/patent/US9986069B2/en'},
    {id:'US9506776B2',title:'Adaptive sampling of smart meter data',summary:'스마트 미터 데이터의 제약 조건에 맞춰 일부 샘플을 선택하는 방법.',tags:['sampling'],section:'청구항 1 · 일부 발췌',quote:'determining a subsample of the meter sensor data;',interpretation:'청구항 1은 제약 조건에 따라 미터 데이터를 수집하고 일부 샘플을 최적화 엔진에 전달하는 구성을 다룹니다.',question:'미터 집단의 시공간 최적화와 단일 단말의 통신 상태 제어는 어떤 점이 다른가요?',url:'https://patents.google.com/patent/US9506776B2/en'},
    {id:'US9268399B2',title:'Adaptive sensor sampling for power efficient context aware inferences',summary:'센서 분류의 신뢰도에 따라 추가 센서를 활성화하는 방법.',tags:['power'],section:'청구항 1 · 일부 발췌',quote:'performing a first classification of the data sample from the first sensor;',interpretation:'청구항 1은 첫 센서의 분류 신뢰도가 기준에 못 미치면 두 번째 센서를 활성화해 함께 분류하는 구성을 다룹니다.',question:'우리의 샘플링 조정 기준은 분류 신뢰도인가요, 통신 품질인가요?',url:'https://patents.google.com/patent/US9268399B2/en'}
  ]
};
