import numpy as np
from .pod import POD


class DMDc:
    """
    Dynamic Mode Decomposition with Control Class

    """

    def __init__(self):

        self.singvals = None
        self.modes = None
        self.time = None
        self.dmd_modes = None
        self.dt = None
        self.t1 = None
        self.n_timesteps = None
        self.tikhonov = None
        self.x_cond = None
        self._kept_rank = None
        self.init = None
        self.input_init = None

    def decompose(self,
                  X,
                  alg="svd",
                  rank=0,
                  opt_trunc=False,
                  tikhonov=0,
                  sorting="abs",
                  Y=None,
                  dt=None,
                  Y_input=None,):
        """Training the dynamic mode decomposition with control model,
                    using the input data X and Y, and Y_input

        Parameters
        ----------
        X : numpy.ndarray
            Snapshot matrix data, of (N, m) size
        Y : numpy.ndarray
            Second Snapshot matrix data, of (N, m) size
            advanced from X by dt
        dt : float
            value of time step from each snapshot in X
            to each snapshot in Y
        alg : str, optional
            Whether to use the SVD on decomposition ("svd") or
            the eigenvalue problem on snaphot matrices ("snap")
            Default : "svd"
        rank : int or float, optional
            if rank = 0 All the ranks are kept, unless their
            singular values are zero
            if 0 < rank < 1, it is used as the percentage of
            the energy that should be kept, and the rank is
            computed accordingly
            Default : 0
        opt_trunc : bool, optional
            if True an optimal truncation/threshold is estimated,
            based on the algorithm of Gavish and Donoho [2]
            Default : False
        tikhonov : int or float, optional
            tikhonov parameter for regularization
            If 0, no regularization is applied, if float, it is used as
            the lambda tikhonov parameter
            Default : 0
        sorting : str, optional
            Whether to sort the discrete DMD eigenvalues by absolute
            value ("abs") or by their real part ("real")
            Default : "abs"
        Y_input : numpy.ndarray
            Control inputs matrix data, of (q, m) size
            organized as 'm' snapshots

        References
        ----------

        [1] On dynamic mode decomposition:  Theory and applications,
        Journal of Computational Dynamics,1,2,391,421,2014-12-1,
        Jonathan H. Tu,Clarence W. Rowley,Dirk M. Luchtenburg,
        Steven L. Brunton,J. Nathan Kutz,2158-2491_2014_2_391,

        [2] M. Gavish and D. L. Donoho, "The Optimal Hard Threshold for
        Singular Values is 4/sqrt(3) ," in IEEE Transactions on Information
        Theory, vol. 60, no. 8, pp. 5040-5053, Aug. 2014,
        doi: 10.1109/TIT.2014.2323359.

        Returns
        ------
        u : numpy.ndarray, of size(N, r)
            The spatial modes of the training data

        s : numpy.ndarray, of size(r, )
            The singular values modes of the training data

        vh : numpy.ndarray, of size(r, m)
            The time dynamics of the training data


        """
        self.tikhonov = tikhonov
        if self.tikhonov:
            self.x_cond = np.linalg.cond(X)

        self.n_timesteps = X.shape[1]
        self.init = X[:, 0]
        self.input_init = Y_input[:, 0]

        # POD Decomposition of the X and Y matrix
        Omega = np.vstack((X, Y_input))
        self.pod_til = POD()
        self.pod_hat = POD()
        u_til, s_til, vh_til = self.pod_til.decompose(
            Omega, alg=alg, rank=rank, opt_trunc=opt_trunc)
        u_til_1 = u_til[: X.shape[0], :]
        u_til_2 = u_til[X.shape[0]::, :]
        u_hat, s_hat, vh_hat = self.pod_hat.decompose(
            Y, alg=alg, rank=rank, opt_trunc=opt_trunc)
        self._kept_rank = self.pod_hat.kept_rank

        s_til_inv = np.zeros(s_til.shape)
        s_til_inv = 1 / s_til
        s_til_inv_ = s_til_inv.copy()
        if self.tikhonov:
            s_til_inv_ *= s_til**2 / (s_til**2 + self.tikhonov * self.x_cond)
        store_ = np.linalg.multi_dot((Y, vh_til.T, np.diag(s_til_inv_)))
        store = u_hat.T @ store_
        self.A_tilde = np.linalg.multi_dot((store, u_til_1.T, u_hat))
        self.B_tilde = store @ u_til_2.T

        # Eigendecomposition on the low dimensional operators
        lambd, w = np.linalg.eig(self.A_tilde)
        if sorting == "abs":
            idx = (np.abs(lambd)).argsort()[::-1]
        else:
            idx = (np.real(lambd)).argsort()[::-1]
        lambd = lambd[idx]
        w = w[:, idx]
        self.low_dim_eig = w

        # Computing the exact DMDc modes
        phi = np.linalg.multi_dot((store_, u_til_1.T, u_hat, w))
        omega = np.log(lambd) / dt

        # Loading the DMDc instance's attributes
        u = u_til_1
        vh = vh_til
        s = s_til
        self.dmd_modes = phi
        self.lambd = lambd
        self.eigenvalues = omega
        self.singvals = s_hat
        self.modes = u
        self.time = vh_hat
        self.u_hat = u_hat

        return u, s, vh

    def predict(self, t, t1=0, rank=None, x_input=None, u_input=None, fixed_input=False, stabilize=False, method=0):
        """Predict the DMD solution on the prescribed time instants.

        Parameters
        ----------
        t: numpy.ndarray, size (nt, )
            time steps at which the DMD solution will be computed
        t1: float
            the value of the time instant of the first snapshot
        rank: int or None
            ranks kept for prediction: it should be a hard threshold integer
            and greater than the rank chose/computed in the decomposition
            phase. If None, the same rank already computed is used
            Default : None
        x_input: numpy.ndarray, size (N, nt)
            state matrix at time steps t. Used for reconstruction
            Adding this flag will disregard the u_input flag
        u_input: numpy.ndarray, size (q, nt)
            control input matrix at time steps t.
        fixed_input: bool, optional
            Specifies if the input conntrol is fixed through time, this
            allows for continuous prediction approach, faster in computation
            when number of ranks excedds ~10
        stabilize : bool, optional
            DMD eigenvalue-shifting to stable eigenvalues at the prediction
            phase
            Default : False
        method: int
            Method used to compute the initial mode amplitudes
            0 if it is computed on the POD subspace as in Tu et al.[1]
            1 if it is computed using the pseudoinverse of the DMD modes
            Default : 0
            
        Returns
        ----------
            numpy.ndarray, size (N, nt)
            DMDc solution on the time values t+dt
        """
        if rank is None:
            rank = self._kept_rank

        init = self.init
        if not fixed_input:
            if x_input is not None:
                return self.u_hat @ (self.A_tilde @ self.u_hat.T @ x_input
                                     + self.B_tilde @ u_input)
            else:
                data = np.zeros(
                    (rank, u_input.shape[1]+1), dtype=complex)
                data[:, 0] = self.u_hat[:, :rank].T @ init
                for i in range(u_input.shape[1]):
                    data[:, i+1] = self.A_tilde[:rank, :rank] @ data[:,
                                                                     i][:rank] + self.B_tilde[:rank, :] @ u_input[:, i]
                data = self.u_hat[:, :rank] @ data
                return data
        else:

            temp, _, _, _ = np.linalg.lstsq(
                self.dmd_modes[:, :rank], self.u_hat[:, :rank] @ self.B_tilde[:rank, :], rcond=None)
            self.control_component = temp

            eig = self.eigenvalues[:rank]
            if stabilize:
                eig_rmpl = eig[np.abs(self.lambd[:rank]) > 1]
                eig_rmpl.real = 0
                eig[np.abs(self.lambd[:rank]) > 1] = eig_rmpl

            if method:
                init = self.init
                b, _, _, _ = np.linalg.lstsq(self.dmd_modes, init, rcond=None)
                b /= np.exp(self.eigenvalues * t1)
            else:
                alpha1 = self.singvals[:rank] * self.time[:rank, 0]
                b = np.linalg.solve(self.lambd[:rank] * self.low_dim_eig[:rank, :rank], alpha1) / np.exp(
                    eig * t1
                )

            return self.dmd_modes[:, :rank] @ ((np.exp(np.outer(eig, t).T) * b).T
                                               - (self.control_component @ u_input[:, 0] / eig)[:, np.newaxis])
