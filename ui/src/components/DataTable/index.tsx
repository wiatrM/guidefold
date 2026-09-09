import type {ReactNode} from 'react';
import css from './DataTable.module.css';

export function DataTable({caption,headings,children,className=''}:{caption:string;headings:string[];children:ReactNode;className?:string}){return <div className={[css.tableRegion,className].join(' ')} tabIndex={0} role="region" aria-label={caption} data-slot="table-container"><table className={css.table} data-slot="table"><caption>{caption}</caption><thead><tr>{headings.map((h,i)=><th scope="col" key={h+i}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;}
