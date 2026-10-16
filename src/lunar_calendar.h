#pragma once
#include "lunar_assets.h"
struct LunarDate {int year,month,day;bool leap;};
inline int civilDays(int y,int m,int d){
 y-=m<=2;int era=y/400,yoe=y-era*400;
 int doy=(153*(m+(m>2?-3:9))+2)/5+d-1;
 return era*146097+yoe*365+yoe/4-yoe/100+doy-719468;
}
inline int lunarMonthDays(int y,int m){return lunarYears[y-1900]&(0x10000>>m)?30:29;}
inline int leapDays(int y){return (lunarYears[y-1900]&15)?((lunarYears[y-1900]&0x10000)?30:29):0;}
inline bool toLunar(int y,int m,int d,LunarDate &out){
 if(y<1900||y>2100||m<1||m>12||d<1||d>31)return false;
 int off=civilDays(y,m,d)-civilDays(1900,1,31);
 if(off<0)return false;
 for(int ly=1900;ly<=2100;ly++){
  int days=leapDays(ly);for(int i=1;i<=12;i++)days+=lunarMonthDays(ly,i);
  if(off>=days){off-=days;continue;}
  for(int lm=1;lm<=12;lm++){
   int n=lunarMonthDays(ly,lm);
   if(off<n){out={ly,lm,off+1,false};return true;}off-=n;
   if((lunarYears[ly-1900]&15)==lm){n=leapDays(ly);if(off<n){out={ly,lm,off+1,true};return true;}off-=n;}
  }
 }
 return false;
}
inline int shichenIndex(int h,int m){return ((h*60+m+60)%1440)/120;}
inline int quarterIndex(int h,int m){return ((h*60+m+60)%120)/15+1;}
