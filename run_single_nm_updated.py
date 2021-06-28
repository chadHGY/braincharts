import os
import sys
import glob
import numpy as np
import pandas as pd
import pickle
import shutil
from matplotlib import pyplot as plt
import statsmodels.api as sm
from scipy import optimize
import seaborn as sns
sns.set(style='whitegrid')

from pcntoolkit.normative import estimate, predict, evaluate
from pcntoolkit.util.utils import create_bspline_basis, compute_MSLL, create_design_matrix
from nm_utils import save_output, test_func, calibration_descriptives

###################################CONFIG #####################################

data_dir = '/Users/andmar/data/sairut/data'
save_im_path = '/Users/andmar/data/sairut/results/'

df_tr = pd.read_csv(os.path.join(data_dir,'lifespan_full_tr.csv'), index_col=0) 
df_te = pd.read_csv(os.path.join(data_dir,'lifespan_full_te.csv'), index_col=0)

# remove some bad subjects
df_tr = df_tr.loc[df_tr['EstimatedTotalIntraCranialVol'] > 0.5]
df_te = df_te.loc[df_te['EstimatedTotalIntraCranialVol'] > 0.5]

cols_cov = ['age','sex'] #'avg_euler_centered_neg_sqrt']
cols_site = df_te.columns.to_list()[222:261]#[234:270]
cols = cols_cov + cols_site

# configure IDPs to use
idp_ids_lh = df_te.columns.to_list()[15:90]
idp_ids_rh = df_te.columns.to_list()[90:165]
idp_ids_sc = df_te.columns.to_list()[165:198]
idp_ids_glob = df_te.columns.to_list()[208:216] + df_te.columns.to_list()[220:222]
idp_ids_all = df_te.columns.to_list()[15:207] + df_te.columns.to_list()[208:222]
idp_ids = ['Right-Hippocampus']
#idp_ids = idp_ids_lh +idp_ids_glob

# run switches
show_plot = True
force_refit = True

# which type of model to run?
cov_type = 'bspline'  # 'int', 'bspline' or None
warp =  'WarpSinArcsinh'   # 'WarpBoxCox', 'WarpSinArcsinh'  or None
sex = 0 # 1 = male 0 = female
if sex == 1: 
    clr = 'blue';
    sex_name = 'male'
else:
    clr = 'red'
    sex_name = 'female'

# cubic B-spline basis (used for regression)
xmin = -5 # boundaries for ages of UKB participants +/- 5
xmax = 110
B = create_bspline_basis(xmin, xmax)#, nknots=10)

################################### RUN #######################################

# create dummy data for visualisation
xx = np.arange(xmin,xmax,0.5)
X0_dummy = np.zeros((len(xx), 2))
X0_dummy[:,0] = xx
X0_dummy[:,1] = sex
for sid, site in enumerate(cols_site):
    print('configuring dummy data for site',sid, site)
    # X_dummy = np.zeros((len(xx), len(cols)))
    # X_dummy[:,0] = xx
    # X_dummy[:,1] = sex
    # #X_dummy[:,2] = df_tr['avg_euler_centered_neg_sqrt'].median()
    # X_dummy[:,sid+len(cols_cov)] = np.ones(len(xx))
    # # add intercept
    # X_dummy = np.concatenate((X_dummy, np.ones((len(xx), 1))), axis=1)
    # # add bspline basis
    # X_dummy = np.concatenate((X_dummy, np.array([B(i) for i in X_dummy[:,0]])), axis=1)

    site_ids = np.zeros((len(xx), len(cols_site)))
    site_ids[:,sid] = 1
    X_dummy = create_design_matrix(X0_dummy, xmin=xmin, xmax=xmax, site_cols=site_ids)
    np.savetxt(os.path.join(data_dir,'cov_bspline_dummy_' + site + '.txt'), X_dummy)


print('configuring dummy data for mean')
# X_dummy = np.zeros((len(xx), len(cols)))
# X_dummy[:,0] = xx
# X_dummy[:,1] = sex
# # add intercept
# X_dummy = np.concatenate((X_dummy, np.ones((len(xx), 1))), axis=1)
# # add bspline basis
# X_dummy = np.concatenate((X_dummy, np.array([B(i) for i in X_dummy[:,0]])), axis=1)

site_ids = np.zeros((len(xx), len(cols_site)))
X_dummy = create_design_matrix(X0_dummy, xmin=xmin, xmax=xmax, site_cols=site_ids)
np.savetxt(os.path.join(data_dir,'cov_bspline_dummy_mean.txt'), X_dummy)


blr_metrics = pd.DataFrame(columns = ['eid', 'NLL', 'EV', 'MSLL', 'BIC'])
nummer = 0
for idp in idp_ids: 
    nummer = nummer + 1
    print(nummer)
    print('Running IDP:', idp)
    idp_dir = os.path.join(data_dir, idp)
    
    # set output dir 
    out_name = 'blr'
    if cov_type is not None:
        out_name += '_' + cov_type
    if warp is not None:
        out_name += '_' + warp
    os.makedirs(os.path.join(idp_dir,out_name), exist_ok=True)
    os.chdir(idp_dir)
    
    # # load data matrices
    # X_tr = df_tr[cols].to_numpy()
    # X_te = df_te[cols].to_numpy()

    # # add intercept column 
    # X_tr = np.concatenate((X_tr, np.ones((X_tr.shape[0],1))), axis=1)
    # X_te = np.concatenate((X_te, np.ones((X_te.shape[0],1))), axis=1)
    
    # # create Bspline basis set 
    # Phi = np.array([B(i) for i in X_tr[:,0]])
    # Phis = np.array([B(i) for i in X_te[:,0]])
    # X_tr = np.concatenate((X_tr, Phi), axis=1)
    # X_te = np.concatenate((X_te, Phis), axis=1)
    
    X_tr = create_design_matrix(df_tr[cols_cov], site_cols = df_tr[cols_site],
                                basis = 'bspline', xmin = xmin, xmax = xmax)
    X_te = create_design_matrix(df_te[cols_cov], site_cols = df_te[cols_site],
                                basis = 'bspline', xmin = xmin, xmax = xmax)
    
    np.savetxt(os.path.join(idp_dir, 'cov_bspline_tr.txt'), X_tr)
    np.savetxt(os.path.join(idp_dir, 'cov_bspline_te.txt'), X_te)
    
    # configure the covariates to use
    if cov_type is None:
        cov_file_tr = os.path.join(idp_dir, 'cov_tr.txt')
        cov_file_te = os.path.join(idp_dir, 'cov_te.txt')
    else:
        cov_file_tr = os.path.join(idp_dir, 'cov_') + cov_type + '_tr.txt'
        cov_file_te = os.path.join(idp_dir, 'cov_') + cov_type + '_te.txt'
    resp_file_tr = os.path.join(idp_dir, 'resp_tr.txt')
    resp_file_te = os.path.join(idp_dir, 'resp_te.txt') 
    
    # configure and save the targets
    y_tr = df_tr[idp].to_numpy() 
    y_te = df_te[idp].to_numpy()
    np.savetxt(resp_file_tr, y_tr)
    np.savetxt(resp_file_te, y_te)
    
    y_tr = y_tr[:, np.newaxis]  
    y_te = y_te[:, np.newaxis]
    Phi_tr = np.loadtxt(cov_file_tr)
    
    resp_tr_skew = calibration_descriptives(np.loadtxt(resp_file_tr))[0]

    w_dir = os.path.join(idp_dir, out_name)
    if not force_refit and os.path.exists(os.path.join(w_dir, 'Models', 'NM_0_0_estimate.pkl')):
        print('Using pre-existing model')
    else:
        w_dir = idp_dir
        if warp == None:
            estimate(cov_file_tr, resp_file_tr, testresp=resp_file_te, 
                     testcov=cov_file_te, alg='blr', configparam=1,
                     optimizer = 'l-bfgs-b', savemodel=True, standardize = False, 
                     hetero_noise = True)
        else: 
             estimate(cov_file_tr, resp_file_tr, testresp=resp_file_te, 
                      testcov=cov_file_te, alg='blr', configparam=1,verbose=True,
                      optimizer = 'l-bfgs-b', savemodel=True, standardize = False, 
                      warp=warp, warp_reparam=True) # if verbose true see inbetween estimates 
        #metrics_new = {'MSLL': 0}
    
    # set up the dummy covariates
    if cov_type is None:
        cov_file_dummy = os.path.join(data_dir, 'cov_dummy')
    else:
        cov_file_dummy = os.path.join(data_dir, 'cov_' + cov_type + '_dummy')
    cov_file_dummy = cov_file_dummy + '_mean.txt'
    
    # make predictions
    yhat, s2 = predict(cov_file_dummy, alg='blr', respfile=None, 
                       model_path=os.path.join(w_dir,'Models'))
    
    with open(os.path.join(w_dir,'Models', 'NM_0_0_estimate.pkl'), 'rb') as handle:
        nm = pickle.load(handle) 
    
    # load test data
    yhat_te = np.loadtxt(os.path.join(w_dir, 'yhat_estimate.txt'))
    s2_te = np.loadtxt(os.path.join(w_dir, 'ys2_estimate.txt'))
    yhat_te = yhat_te[:, np.newaxis]
    s2_te = s2_te[:, np.newaxis]
    X_te = np.loadtxt(cov_file_te)
    
    if warp is None:
        # compute evaluation metrics
        metrics = evaluate(y_te, yhat_te)  
        
        # compute MSLL manually as a sanity check
        y_tr_mean = np.array( [[np.mean(y_tr)]] )
        y_tr_var = np.array( [[np.var(y_tr)]] )
        MSLL = compute_MSLL(y_te, yhat_te, s2_te, y_tr_mean, y_tr_var)         
     
    else:
        warp_param = nm.blr.hyp[1:nm.blr.warp.get_n_params()+1] 
        W = nm.blr.warp
        
        # warp and plot dummy predictions
        med, pr_int = W.warp_predictions(np.squeeze(yhat), np.squeeze(s2), warp_param)
        
        # warp predictions
        med_te = W.warp_predictions(np.squeeze(yhat_te), np.squeeze(s2_te), warp_param)[0]
        med_te = med_te[:, np.newaxis]
       
        # evaluation metrics
        metrics = evaluate(y_te, med_te)
        
        # compute MSLL manually
        y_te_w = W.f(y_te, warp_param)
        y_tr_w = W.f(y_tr, warp_param)
        y_tr_mean = np.array( [[np.mean(y_tr_w)]] )
        y_tr_var = np.array( [[np.var(y_tr_w)]] )
        MSLL = compute_MSLL(y_te_w, yhat_te, s2_te, y_tr_mean, y_tr_var)     
  
    y_te_rescaled_all = np.zeros_like(y_te)
    for sid, site in enumerate(cols_site):
                
        # plot the true test data points
        #idx = np.where(np.bitwise_and(X_te[:,1] == sex, X_te[:,sid+len(cols_cov)] !=0))
        idx = np.where(np.bitwise_and(X_te[:,2] == sex, X_te[:,sid+len(cols_cov)+1] !=0))
    
        # load training data (needed for MSLL)
        #idx_dummy = np.bitwise_and(X_dummy[:,0] > X_te[idx,0].min(), X_dummy[:,0] < X_te[idx,0].max())
        idx_dummy = np.bitwise_and(X_dummy[:,1] > X_te[idx,1].min(), X_dummy[:,1] < X_te[idx,1].max())
        
        # adjust the intercept
        if warp is None:
            y_te_rescaled = y_te[idx] - np.median(y_te[idx]) + np.median(yhat[idx_dummy])
        else:            
            y_te_rescaled = y_te[idx] - np.median(y_te[idx]) + np.median(med[idx_dummy])
        #y_te_rescaled = y_te[idx]
        if show_plot:
            #plt.scatter(X_te[idx,0], y_te_rescaled, s=7, color=clr, alpha = 0.1)   
            plt.scatter(X_te[idx,1], y_te_rescaled, s=7, color=clr, alpha = 0.1)   
        y_te_rescaled_all[idx] = y_te_rescaled
    
    #idx_all = np.where(X_te[:,1] == sex)
    #sns.jointplot(x=X_te[idx_all,0].ravel(), y=np.log(y_te_rescaled_all[idx_all].ravel()), kind="hex")
    #plt.hexbin(X_te[idx_all,0].ravel(), y_te_rescaled_all[idx_all].ravel(), cmap=plt.cm.Blues, gridsize=40, alpha=0.5)
    #sns.kdeplot(x=X_te[idx_all,0].ravel(), y=np.log(y_te_rescaled_all[idx_all].ravel()))
    
    if warp is None:
        if show_plot:
            plt.plot(xx, yhat, color = clr)
            plt.fill_between(xx, np.squeeze(yhat-0.67*np.sqrt(s2)), 
                             np.squeeze(yhat+0.67*np.sqrt(s2)), 
                             color=clr, alpha = 0.1)
            plt.fill_between(xx, np.squeeze(yhat-1.64*np.sqrt(s2)), 
                             np.squeeze(yhat+1.64*np.sqrt(s2)), 
                             color=clr, alpha = 0.1)
            plt.fill_between(xx, np.squeeze(yhat-2.33*np.sqrt(s2)), 
                             np.squeeze(yhat+2.32*np.sqrt(s2)), 
                             color=clr, alpha = 0.1)
            plt.plot(xx, np.squeeze(yhat-0.67*np.sqrt(s2)),color=clr, linewidth=0.5)
            plt.plot(xx, np.squeeze(yhat+0.67*np.sqrt(s2)),color=clr, linewidth=0.5)
            plt.plot(xx, np.squeeze(yhat-1.64*np.sqrt(s2)),color=clr, linewidth=0.5)
            plt.plot(xx, np.squeeze(yhat+1.64*np.sqrt(s2)),color=clr, linewidth=0.5)
            plt.plot(xx, np.squeeze(yhat-2.33*np.sqrt(s2)),color=clr, linewidth=0.5)
            plt.plot(xx, np.squeeze(yhat+2.32*np.sqrt(s2)),color=clr, linewidth=0.5)
    else:
        warp_param = nm.blr.hyp[1:nm.blr.warp.get_n_params()+1] 
        W = nm.blr.warp
        
        # warp and plot dummy predictions
        med, pr_int = W.warp_predictions(np.squeeze(yhat), np.squeeze(s2), warp_param)
        
        # plot the centiles
        junk, pr_int25 = W.warp_predictions(np.squeeze(yhat), np.squeeze(s2), warp_param, percentiles=[0.25,0.75])
        junk, pr_int95 = W.warp_predictions(np.squeeze(yhat), np.squeeze(s2), warp_param, percentiles=[0.05,0.95])
        junk, pr_int99 = W.warp_predictions(np.squeeze(yhat), np.squeeze(s2), warp_param, percentiles=[0.01,0.99])
        
        if show_plot: 
            plt.plot(xx, med, clr)
            #plt.fill_between(xx, pr_int[:,0], pr_int[:,1], alpha = 0.2,color=clr)
            plt.fill_between(xx, pr_int25[:,0], pr_int25[:,1], alpha = 0.1,color=clr)
            plt.fill_between(xx, pr_int95[:,0], pr_int95[:,1], alpha = 0.1,color=clr)
            plt.fill_between(xx, pr_int99[:,0], pr_int99[:,1], alpha = 0.1,color=clr)
            plt.plot(xx, pr_int25[:,0],color=clr, linewidth=0.5)
            plt.plot(xx, pr_int25[:,1],color=clr, linewidth=0.5)
            plt.plot(xx, pr_int95[:,0],color=clr, linewidth=0.5)
            plt.plot(xx, pr_int95[:,1],color=clr, linewidth=0.5)
            plt.plot(xx, pr_int99[:,0],color=clr, linewidth=0.5)
            plt.plot(xx, pr_int99[:,1],color=clr, linewidth=0.5)


    if show_plot:
        plt.xlabel('Age')
        plt.ylabel(idp) 
        plt.title(idp)
        plt.xlim((0,90))
        plt.savefig(os.path.join(idp_dir, out_name, 'centiles_' + str(sex)),  bbox_inches='tight')
        plt.show()
     
    BIC = len(nm.blr.hyp) * np.log(y_tr.shape[0]) + 2 * nm.neg_log_lik
    
    # print -log(likelihood)
    print('NLL =', nm.neg_log_lik)
    print('BIC =', BIC)
    print('EV = ', metrics['EXPV'])
    print('MSLL = ', MSLL) 
    
    blr_metrics.loc[len(blr_metrics)] = [idp, nm.neg_log_lik, 
                                         metrics['EXPV'][0], MSLL[0], BIC]
  
    # save blr stuff
    save_output(idp_dir, os.path.join(idp_dir, out_name))
    
    if show_plot:
        Z = np.loadtxt(os.path.join(idp_dir, out_name, 'Z_estimate.txt'))
        [skew, sdskew, kurtosis, sdkurtosis, semean, sesd] = calibration_descriptives(Z)
        plt.figure()
        plt.hist(Z, bins = 100, label = 'skew = ' + str(round(skew,3)) + ' kurtosis = ' + str(round(kurtosis,3)))
        plt.title('Z_warp ' + idp)
        plt.legend()
        plt.savefig(os.path.join(idp_dir, out_name, 'Z_hist'),  bbox_inches='tight')
        plt.show()
    
        plt.figure()
        sm.qqplot(Z, line = '45')
        plt.savefig(os.path.join(idp_dir, out_name, 'Z_qq'),  bbox_inches='tight')
        plt.show()
#blr_metrics.to_pickle(os.path.join(data_dir,'metrics_' + out_name + '.pkl'))

print(nm.blr.hyp)

