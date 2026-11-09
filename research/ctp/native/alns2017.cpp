// Independent reconstruction of Vargas/Jozefowiez/Ngueveu2017.
// See fidelity ledger; not original author code, no claim of identical runtime.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <memory>
#include <numeric>
#include <queue>
#include <random>
#include <stdexcept>
#include <vector>
using namespace std;
using Mask=array<uint64_t,16>;using Clock=chrono::steady_clock;
Mask uni(Mask a,const Mask& b){for(int i=0;i<16;i++)a[i]|=b[i];return a;}
bool sup(const Mask&a,const Mask&b){for(int i=0;i<16;i++)if((a[i]|b[i])!=a[i])return false;return true;}
int uncovered(const Mask&a,const Mask&b){int k=0;for(int i=0;i<16;i++)k+=__builtin_popcountll(b[i]&~a[i]);return k;}
struct Answer{long long cost;vector<int> route;bool exact=true;long long created=0,expanded=0;};
struct Problem{int n,m;vector<vector<int>> c;vector<Mask> cover;Mask full{};
 long long cost(const vector<int>&r)const{long long x=0;for(size_t i=0;i<r.size();i++)x+=c[r[i]][r[(i+1)%r.size()]];return x;}
 bool feasible(const vector<int>&r)const{if(r.size()<3||r[0]!=0)return false;Mask x{};vector<int> seen(n);for(int v:r){if(v<0||v>=n||seen[v]++)return false;x=uni(x,cover[v]);}return x==full;}
};
Answer upper_bound_tour(const Problem&d,const vector<int>&o){
 Answer best{d.cost(o),o};int n=d.n;
 // Algorithm4 family: first nondepot i, optional skipped prefix after i,
 // then extend adjacent useful successors. Every incumbent audited below.
 for(int i=1;i<n;i++)for(int k=i;k<n;k++){
  vector<int>r{0,o[i]};Mask mask=uni(d.cover[0],d.cover[o[i]]);
  for(int j=k+1;j<n;j++){
   if(uncovered(mask,d.cover[o[j]])||r.size()<3){r.push_back(o[j]);mask=uni(mask,d.cover[o[j]]);}
   if(mask==d.full&&r.size()>=3){long long v=d.cost(r);if(v<best.cost)best={v,r};break;}
  }
  if(mask==d.full&&r.size()>=3){long long v=d.cost(r);if(v<best.cost)best={v,r};}
 }
 return best;
}
struct Label{long long cost;Mask covered;vector<int> path;int rank,side;double key;bool alive=true;};
struct Less{bool operator()(const shared_ptr<Label>&a,const shared_ptr<Label>&b)const{return a->key>b->key;}};
Answer selector(const Problem&d,const vector<int>&order,bool bi,double deadline_seconds,Clock::time_point began,long long maxlabels=2000000){
 Answer best=upper_bound_tour(d,order);vector<int> rev{0};for(int i=d.n-1;i>0;i--)rev.push_back(order[i]);array<vector<int>,2> ord{order,rev};
 vector<vector<vector<shared_ptr<Label>>>> bucket(2,vector<vector<shared_ptr<Label>>>(d.n));
 array<vector<Mask>,2> suffix;
 for(int side=0;side<2;side++){suffix[side].resize(d.n+1);for(int i=d.n-1;i>=0;i--)suffix[side][i]=uni(suffix[side][i+1],d.cover[ord[side][i]]);}
 auto bound=[&](const Label&l){
  if(!bi)return 0.0;
  int need=uncovered(l.covered,d.full);if(!need)return 0.0;
  vector<pair<double,int>> objects;auto&o=ord[l.side];
  for(int j=l.rank+1;j<d.n;j++){
   int profit=uncovered(l.covered,d.cover[o[j]]);if(!profit)continue;
   int incoming=d.c[o[l.rank]][o[j]],outgoing=d.c[o[j]][0];
   for(int k=l.rank+1;k<j;k++)incoming=min(incoming,d.c[o[k]][o[j]]);
   for(int k=j+1;k<d.n;k++)outgoing=min(outgoing,d.c[o[j]][o[k]]);
   // Half incident-edge weights prevent counting remaining-remaining edges twice.
   double weight=.5*(incoming+outgoing);objects.push_back({weight/profit,profit});
  }
  sort(objects.begin(),objects.end());double value=0;for(auto [ratio,p]:objects){int take=min(need,p);value+=ratio*take;need-=take;if(!need)break;}return need?1e100:value;
 };
 priority_queue<shared_ptr<Label>,vector<shared_ptr<Label>>,Less> heap;
 for(int s=0;s<(bi?2:1);s++){auto p=make_shared<Label>(Label{0,d.cover[0],{0},0,s,0});bucket[s][0].push_back(p);heap.push(p);best.created++;}
 while(!heap.empty()){
  if(chrono::duration<double>(Clock::now()-began).count()>=deadline_seconds||best.created>=maxlabels){best.exact=false;break;}
  auto l=heap.top();heap.pop();if(!l->alive||l->key>=best.cost-1e-9)continue;best.expanded++;auto&o=ord[l->side];
  for(int j=l->rank+1;j<d.n;j++){
   int v=o[j];long long cost=l->cost+d.c[o[l->rank]][v];if(cost>=best.cost)continue;
   Mask mask=uni(l->covered,d.cover[v]);if(!sup(uni(mask,suffix[l->side][j+1]),d.full))continue;
   auto path=l->path;path.push_back(v);
   if(mask==d.full&&path.size()>=3&&cost+d.c[v][0]<best.cost){best.cost=cost+d.c[v][0];best.route=path;}
   int cardinality=min(3,(int)path.size());bool dominated=false;auto&q=bucket[l->side][v];
   for(auto&a:q)if(a->alive&&min(3,(int)a->path.size())==cardinality&&a->cost<=cost&&sup(a->covered,mask)){dominated=true;break;}
   if(dominated)continue;
   for(auto&a:q)if(a->alive&&min(3,(int)a->path.size())==cardinality&&cost<=a->cost&&sup(mask,a->covered))a->alive=false;
   auto next=make_shared<Label>(Label{cost,mask,path,j,l->side,(double)cost});next->key+=bound(*next);q.push_back(next);best.created++;
   if(bi)for(auto&a:bucket[1-l->side][v])if(a->alive&&mask!=d.full&&uni(mask,a->covered)==d.full&&path.size()+a->path.size()-2>=3&&cost+a->cost<best.cost){
    auto f=l->side==0?path:a->path;auto b=l->side==0?a->path:path;
    for(int k=(int)b.size()-2;k>=1;k--){f.push_back(b[k]);}
    if(d.feasible(f)){best.cost=d.cost(f);best.route=f;}
   }
   if(next->key<best.cost-1e-9)heap.push(next);
  }
 }
 if(!d.feasible(best.route)||d.cost(best.route)!=best.cost)throw runtime_error("Selector invalid route");
 return best;
}
void twoopt(const Problem&d,vector<int>&r){bool change=true;while(change){change=false;for(int i=1;i<d.n-1&&!change;i++)for(int j=i+1;j<d.n;j++)if(d.c[r[i-1]][r[i]]+d.c[r[j]][r[(j+1)%d.n]]>d.c[r[i-1]][r[j]]+d.c[r[i]][r[(j+1)%d.n]]){reverse(r.begin()+i,r.begin()+j+1);change=true;break;}}}
struct Params{int segment,shaw,worst,k1,k2,k3;};
int main(int argc,char**argv){try{
 if(argc<5)throw runtime_error("usage mode[M|B|SELECT_M|SELECT_B|UB] seed iterations safety_seconds [label_limit]");
 string mode=argv[1];bool bi=mode=="B"||mode=="SELECT_B";int seed=stoi(argv[2]),iterations=stoi(argv[3]);double safety=stod(argv[4]);long long cap=argc>5?stoll(argv[5]):2000000;auto began=Clock::now();
 Problem d;cin>>d.n>>d.m;if(d.m>1024||d.n<3)throw runtime_error("input size");d.c.assign(d.n,vector<int>(d.n));for(auto&r:d.c)for(int&x:r)cin>>x;d.cover.resize(d.n);for(int i=0;i<d.n;i++)for(int j=0;j<d.m;j++){int x;cin>>x;if(x)d.cover[i][j/64]|=1ULL<<(j%64);}for(int j=0;j<d.m;j++)d.full[j/64]|=1ULL<<(j%64);
 vector<int> order(d.n);iota(order.begin(),order.end(),0);if(mode.rfind("SELECT",0)==0||mode=="UB"){for(int&v:order)cin>>v;auto a=mode=="UB"?upper_bound_tour(d,order):selector(d,order,bi,safety,began,cap);cout<<"{\"cost\":"<<a.cost<<",\"exact\":"<<(a.exact?"true":"false")<<",\"labels\":"<<a.created<<",\"route\":[";for(size_t i=0;i<a.route.size();i++)cout<<(i?",":"")<<a.route[i];cout<<"]}"<<endl;return 0;}
 mt19937 rng(seed);auto uniform=[&](){return generate_canonical<double,53>(rng);};shuffle(order.begin()+1,order.end(),rng);twoopt(d,order);double temperature=d.cost(order);auto boundbest=upper_bound_tour(d,order);Answer best=selector(d,order,bi,safety,began,cap);long long currentcost=best.cost;vector<int> current=order;bool complete=best.exact;long long selector_calls=1,labels=best.created,improvements=0;int completed=0;
 Params p=bi?Params{75,6,3,40,25,15}:Params{100,7,2,60,25,15};array<double,3> rw{1,1,1},iw{1,1,1},rs{},is{};array<int,3> rc{},ic{};array<long long,3> rtotal{},itotal{};
 auto roulette=[&](auto&w){return (int)discrete_distribution<int>(w.begin(),w.end())(rng);};
 cout<<"{\"event\":\"initial\",\"cost\":"<<best.cost<<"}"<<endl;
 for(int it=1;it<=iterations&&complete;it++){
  if(chrono::duration<double>(Clock::now()-began).count()>=safety){complete=false;break;}
  int removal=roulette(rw),insertion=roulette(iw);rc[removal]++;ic[insertion]++;rtotal[removal]++;itotal[insertion]++;vector<int> partial=current,removed;
  int lo=max(1,(int)ceil(.3*d.n)),hi=min(d.n-1,(int)floor(.5*d.n));int q=uniform_int_distribution<int>(lo,max(lo,hi))(rng);
  if(removal==0){int first=uniform_int_distribution<int>(1,d.n-1)(rng);removed.push_back(partial[first]);partial.erase(partial.begin()+first);}
  while((int)removed.size()<q){int index=1;if(removal==2)index=uniform_int_distribution<int>(1,(int)partial.size()-1)(rng);
   else{vector<pair<int,int>>scores;int reference=removal==0?removed[uniform_int_distribution<int>(0,(int)removed.size()-1)(rng)]:0;
    for(int j=1;j<(int)partial.size();j++){int value=removal==0?d.c[reference][partial[j]]:-(d.c[partial[j-1]][partial[j]]+d.c[partial[j]][partial[(j+1)%partial.size()]]-d.c[partial[j-1]][partial[(j+1)%partial.size()]]);scores.push_back({value,j});}
    sort(scores.begin(),scores.end());int rank=min((int)scores.size()-1,(int)(pow(uniform(),removal==0?p.shaw:p.worst)*scores.size()));index=scores[rank].second;
   }removed.push_back(partial[index]);partial.erase(partial.begin()+index);
  }
  while(!removed.empty()){
   int choose=0,position=1;long long chosen=insertion==2?numeric_limits<long long>::min():numeric_limits<long long>::max();
   for(int k=0;k<(int)removed.size();k++){
    if(insertion==1&&k>0)break;
    vector<pair<int,int>>slots;
    for(int j=1;j<=(int)partial.size();j++){int a=partial[j-1],b=partial[j%partial.size()],v=removed[k];slots.push_back({d.c[a][v]+d.c[v][b]-d.c[a][b],j});}sort(slots.begin(),slots.end());
    // Regret-2; k is unspecified in the 2017 article, recorded in ledger.
    long long value=insertion==2?(slots.size()>1?slots[1].first-slots[0].first:0):slots[0].first;
    if((insertion==2&&value>chosen)||(insertion!=2&&value<chosen)){chosen=value;choose=k;position=slots[0].second;}
   }partial.insert(partial.begin()+position,removed[choose]);removed.erase(removed.begin()+choose);
  }
  auto candidate=upper_bound_tour(d,partial);
  if(candidate.cost<boundbest.cost){boundbest=candidate;candidate=selector(d,partial,bi,safety,began,cap);selector_calls++;labels+=candidate.created;if(!candidate.exact){complete=false;break;}}
  double reward=0;bool accept=false;
  if(candidate.cost<best.cost){best=candidate;reward=p.k1;improvements++;cout<<"{\"event\":\"improvement\",\"iteration\":"<<it<<",\"cost\":"<<best.cost<<"}"<<endl;}
  else if(candidate.cost<currentcost)reward=p.k2;
  if(candidate.cost<currentcost||uniform()<exp(min(0.0,(currentcost-candidate.cost)/max(temperature,1e-300)))){accept=true;if(!reward)reward=p.k3;}
  if(accept){current=partial;currentcost=candidate.cost;rs[removal]+=reward;is[insertion]+=reward;}
  temperature*=.99999;completed=it;
  if(it%p.segment==0){for(int k=0;k<3;k++){if(rc[k])rw[k]=.6*rw[k]+.4*rs[k]/rc[k];if(ic[k])iw[k]=.6*iw[k]+.4*is[k]/ic[k];rw[k]=max(rw[k],1e-12);iw[k]=max(iw[k],1e-12);}rs={};is={};rc={};ic={};}
  if(it==1000||it%5000==0)cout<<"{\"event\":\"checkpoint\",\"iteration\":"<<it<<",\"cost\":"<<best.cost<<",\"seconds\":"<<chrono::duration<double>(Clock::now()-began).count()<<"}"<<endl;
 }
 if(!d.feasible(best.route))throw runtime_error("Invalid ALNS route");
 cout<<"{\"event\":\"final\",\"mode\":\""<<mode<<"\",\"seed\":"<<seed<<",\"iterations\":"<<completed<<",\"complete\":"<<(complete&&completed==iterations?"true":"false")<<",\"cost\":"<<best.cost<<",\"selector_calls\":"<<selector_calls<<",\"labels\":"<<labels<<",\"wall_seconds\":"<<chrono::duration<double>(Clock::now()-began).count()<<",\"removal_calls\":["<<rtotal[0]<<","<<rtotal[1]<<","<<rtotal[2]<<"],\"insertion_calls\":["<<itotal[0]<<","<<itotal[1]<<","<<itotal[2]<<"],\"route\":[";for(size_t i=0;i<best.route.size();i++)cout<<(i?",":"")<<best.route[i];cout<<"]}"<<endl;
 }catch(exception&e){cerr<<e.what()<<endl;return 1;}}
