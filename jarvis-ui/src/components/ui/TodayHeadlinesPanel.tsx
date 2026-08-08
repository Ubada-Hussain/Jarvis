import React from 'react';
import { Panel } from './Panel';

const news = [
  "SpaceX IPO raises $85.7B, valuation surpasses $2T.",
  "Apple CEO announces price hikes due to memory costs.",
  "Fox Corporation to acquire Roku for $22B."
];

export const TodayHeadlinesPanel: React.FC = () => {
  return (
    <Panel 
      title="TODAY HEADLINES" 
      headerRight={
        <div className="flex gap-2">
          <span className="cursor-pointer hover:text-red-500">⟳</span>
          <span className="cursor-pointer hover:text-red-500">⛶</span>
        </div>
      }
      className="h-[250px]"
    >
      <div className="p-4 flex flex-col gap-4">
        {news.map((item, index) => (
          <div key={index} className="flex gap-3 text-sm">
            <span className="text-red-700 font-bold tracking-widest text-xs mt-0.5">
              {(index + 1).toString().padStart(2, '0')}
            </span>
            <p className="text-red-500/80 leading-relaxed text-xs">
              {item}
            </p>
          </div>
        ))}
      </div>
    </Panel>
  );
};
